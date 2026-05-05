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
            "dnf install -y java-25-amazon-corretto-headless wget",
            "mkdir -p /opt/minecraft",
            "cd /opt/minecraft",
            # Check latest vanilla server URL manually from minecraft.net if needed
            "wget -O server.jar https://piston-data.mojang.com/v1/objects/97ccd4c0ed3f81bbb7bfacddd1090b0c56f9bc51/server.jar",
            "echo 'eula=true' > eula.txt",
            "cat > server.properties <<'EOF'\n"
            "server-port=25565\n"
            "online-mode=true\n"
            "white-list=false\n"
            "enforce-whitelist=false\n"
            "motd=CDK Minecraft Server\n"
            "view-distance=8\n"
            "simulation-distance=6\n"
            "EOF",
            "cat > /etc/systemd/system/minecraft.service <<'EOF'\n"
            "[Unit]\n"
            "Description=Minecraft Server\n"
            "After=network.target\n\n"
            "[Service]\n"
            "WorkingDirectory=/opt/minecraft\n"
            "ExecStart=/usr/bin/java -Xms1G -Xmx3G -jar server.jar nogui\n"
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
