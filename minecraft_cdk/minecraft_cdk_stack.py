# minecraft_cdk/minecraft_cdk_stack.py
from aws_cdk import (
    Stack,
    CfnOutput,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_elasticloadbalancingv2_targets as targets,
)
from constructs import Construct

# A CDK Stack is the unit of deployment — everything defined inside one Stack
# gets deployed together as a single CloudFormation stack.
class MinecraftCdkStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # A VPC (Virtual Private Cloud) is a private network inside AWS.
        # All our resources live inside it. max_azs=1 keeps things simple and
        # cheap by using only one Availability Zone. nat_gateways=0 avoids the
        # ~$30/month NAT gateway charge — the EC2 instance uses a public IP
        # instead for outbound internet access.
        vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=1,
            nat_gateways=0,
        )

        # The EC2 instance is the virtual machine that will run the Minecraft server.
        # t3.medium gives us 2 vCPUs and 4 GB RAM — enough headroom for a small server.
        # We place it in the public subnet so it can reach the internet without a NAT gateway.
        # The 20 GB EBS volume is the root disk where the OS and server files live.
        instance = ec2.Instance(
            self,
            "MinecraftServer",
            vpc=vpc,
            instance_type=ec2.InstanceType("t3.medium"),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(20),
                )
            ],
        )

        # User data is a shell script that runs automatically the first time the
        # instance boots. This is how we install and configure the Minecraft server
        # without ever SSHing into the machine manually.
        instance.user_data.add_commands(
            "dnf update -y",
            "dnf install -y java-25-amazon-corretto-headless wget curl jq",
            "mkdir -p /opt/minecraft/plugins",
            "cd /opt/minecraft",

            # Pick the Paper server version you want to run.
            # Use the newest Paper version your server should be on.
            "MC_VERSION=1.21.11",

            # Download latest Paper build for that Minecraft version.
            "PAPER_BUILD=$(curl -fsSL https://api.papermc.io/v2/projects/paper/versions/${MC_VERSION}/builds | jq -r '.builds[-1].build')",
            "wget -O paper.jar https://api.papermc.io/v2/projects/paper/versions/${MC_VERSION}/builds/${PAPER_BUILD}/downloads/paper-${MC_VERSION}-${PAPER_BUILD}.jar",

            # Install ViaVersion + ViaBackwards.
            # These plugins let players on different Minecraft client versions connect
            # to the same server, so everyone doesn't need to be on the exact same version.
            "wget -O plugins/ViaVersion.jar https://hangarcdn.papermc.io/plugins/ViaVersion/ViaVersion/versions/5.9.0/PAPER/ViaVersion-5.9.0.jar",
            "wget -O plugins/ViaBackwards.jar https://hangarcdn.papermc.io/plugins/ViaVersion/ViaBackwards/versions/5.9.0/PAPER/ViaBackwards-5.9.0.jar",

            # Mojang requires accepting the EULA before the server will start.
            "echo 'eula=true' > eula.txt",

            # Write the server configuration file.
            # online-mode=false means players don't need a paid Minecraft account to join.
            "cat > server.properties <<'EOF'\n"
            "server-port=25565\n"
            "online-mode=false\n"
            "white-list=false\n"
            "enforce-whitelist=false\n"
            "motd=CDK Paper Minecraft Server\n"
            "view-distance=8\n"
            "simulation-distance=6\n"
            "gamemode=creative\n"
            "force-gamemode=true\n"
            "difficulty=peaceful\n"
            "spawn-protection=0\n"
            "enable-command-block=true\n"
            "pvp=false\n"
            "allow-flight=true\n"
            "allow-world-teleport=true",
            "op-permission-level=4",
            "EOF",

            # Register the Minecraft server as a systemd service so it starts
            # automatically on boot and restarts itself if it crashes.
            "cat > /etc/systemd/system/minecraft.service <<'EOF'\n"
            "[Unit]\n"
            "Description=Paper Minecraft Server\n"
            "After=network.target\n\n"
            "[Service]\n"
            "WorkingDirectory=/opt/minecraft\n"
            "ExecStart=/usr/bin/java -Xms1G -Xmx3G -jar paper.jar nogui\n"
            "Restart=always\n"
            "User=root\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
            "EOF",

            "systemctl daemon-reload",
            "systemctl enable minecraft",
            "systemctl start minecraft",
        )

        # A Network Load Balancer (NLB) sits in front of the EC2 instance and gives
        # us a stable DNS hostname. Without it, the server address would change every
        # time the instance is stopped and restarted, because EC2 reassigns public IPs.
        nlb = elbv2.NetworkLoadBalancer(
            self,
            "MinecraftNLB",
            vpc=vpc,
            internet_facing=True,
        )

        # A target group is the NLB's list of backends to send traffic to.
        # The health check periodically opens a TCP connection to port 25565 — if
        # it fails, the NLB stops sending players to that instance.
        target_group = elbv2.NetworkTargetGroup(
            self,
            "MinecraftTargetGroup",
            vpc=vpc,
            port=25565,
            protocol=elbv2.Protocol.TCP,
            target_type=elbv2.TargetType.INSTANCE,
            health_check=elbv2.HealthCheck(
                enabled=True,
                protocol=elbv2.Protocol.TCP,
                port="25565",
            ),
        )

        # Register our EC2 instance as the target on port 25565.
        target_group.add_target(targets.InstanceTarget(instance, 25565))

        # A listener is the port the NLB accepts incoming connections on.
        # It receives TCP traffic on 25565 and forwards it to the target group.
        nlb.add_listener(
            "MinecraftListener",
            port=25565,
            protocol=elbv2.Protocol.TCP,
            default_target_groups=[target_group],
        )

        # Open port 25565 to the internet on the NLB, and allow the NLB to
        # forward that traffic on to the EC2 instance.
        nlb.connections.allow_from_any_ipv4(ec2.Port.tcp(25565))
        nlb.connections.allow_to(instance, ec2.Port.tcp(25565))

        # Print the NLB's DNS name after deployment — this is the address
        # players type into Minecraft to join the server.
        CfnOutput(self, "ServerAddress", value=nlb.load_balancer_dns_name)
