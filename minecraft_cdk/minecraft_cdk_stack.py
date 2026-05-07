# minecraft_cdk/minecraft_cdk_stack.py
from aws_cdk import (
    Stack,
    CfnOutput,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_elasticloadbalancingv2_targets as targets,
)
from constructs import Construct

class MinecraftCdkStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=1,
            nat_gateways=0,
        )

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
            "wget -O plugins/ViaVersion.jar https://hangarcdn.papermc.io/plugins/ViaVersion/ViaVersion/versions/5.9.0/PAPER/ViaVersion-5.9.0.jar",
            "wget -O plugins/ViaBackwards.jar https://hangarcdn.papermc.io/plugins/ViaVersion/ViaBackwards/versions/5.9.0/PAPER/ViaBackwards-5.9.0.jar",

            "echo 'eula=true' > eula.txt",
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

        # Create Network Load Balancer for stable external endpoint
        nlb = elbv2.NetworkLoadBalancer(
            self,
            "MinecraftNLB",
            vpc=vpc,
            internet_facing=True,
        )

        # Create target group for Minecraft server (TCP port 25565)
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

        # Add EC2 instance as target
        target_group.add_target(targets.InstanceTarget(instance, 25565))

        # Add listener to NLB
        nlb.add_listener(
            "MinecraftListener",
            port=25565,
            protocol=elbv2.Protocol.TCP,
            default_target_groups=[target_group],
        )

        nlb.connections.allow_from_any_ipv4( ec2.Port.tcp(25565))
        nlb.connections.allow_to(instance, ec2.Port.tcp(25565))
        CfnOutput(self, "ServerAddress", value=nlb.load_balancer_dns_name)
