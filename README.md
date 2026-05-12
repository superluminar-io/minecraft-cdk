
# Minecraft CDK

This project provisions a fully playable Minecraft server on AWS using the AWS CDK (Python). The goal is to treat game server infrastructure the same way you would treat any other cloud workload: defined as code, repeatable, and deployable with a single command.

Instead of manually spinning up a server, configuring it by hand, and losing that configuration the moment the instance is replaced, everything here is declared in code. Running `cdk deploy` stands up the complete stack from scratch — VPC, EC2 instance, Network Load Balancer, and the Minecraft server software installed and running as a systemd service.

The server runs [Paper](https://papermc.io/), a high-performance fork of Minecraft's server software, with [ViaVersion](https://hangarcdn.papermc.io/plugins/ViaVersion/ViaVersion) and [ViaBackwards](https://hangarcdn.papermc.io/plugins/ViaVersion/ViaBackwards) installed so players on different client versions can connect. A Network Load Balancer sits in front of the instance to provide a stable DNS hostname — the address players use to connect never changes, even if the underlying EC2 instance is replaced.

## Architecture

```
  Minecraft Players
        │
        │  TCP :25565
        ▼
┌───────────────────────────────────────────────────────────┐
│ AWS                                                        │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ VPC  (single AZ · no NAT gateway)                   │  │
│  │  ┌───────────────────────────────────────────────┐  │  │
│  │  │ Public Subnet                                  │  │  │
│  │  │                                                │  │  │
│  │  │  ┌──────────────────────┐                     │  │  │
│  │  │  │ Network Load         │                     │  │  │
│  │  │  │ Balancer             │                     │  │  │
│  │  │  │ (internet-facing)    │                     │  │  │
│  │  │  │ TCP :25565           │                     │  │  │
│  │  │  └──────────┬───────────┘                     │  │  │
│  │  │             │ Target Group  TCP :25565         │  │  │
│  │  │             ▼                                  │  │  │
│  │  │  ┌──────────────────────┐                     │  │  │
│  │  │  │ EC2  t3.medium       │                     │  │  │
│  │  │  │ Amazon Linux 2023    │                     │  │  │
│  │  │  │ 20 GB EBS            │                     │  │  │
│  │  │  │ ─────────────────    │                     │  │  │
│  │  │  │ Paper 1.21.11        │                     │  │  │
│  │  │  │ ViaVersion 5.9.0     │                     │  │  │
│  │  │  │ ViaBackwards 5.9.0   │                     │  │  │
│  │  │  │ (systemd · Java 25)  │                     │  │  │
│  │  │  └──────────────────────┘                     │  │  │
│  │  └───────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                            │
│  Output: NLB DNS name  ◄── use this as your server address │
└───────────────────────────────────────────────────────────┘
```

The `cdk.json` file tells the CDK Toolkit how to execute your app.

This project is set up like a standard Python project.  The initialization
process also creates a virtualenv within this project, stored under the `.venv`
directory.  To create the virtualenv it assumes that there is a `python3`
(or `python` for Windows) executable in your path with access to the `venv`
package. If for any reason the automatic creation of the virtualenv fails,
you can create the virtualenv manually.

To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .venv/bin/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

To add additional dependencies, for example other CDK libraries, just add
them to your `requirements.txt` file and rerun the `python -m pip install -r requirements.txt`
command.

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation

Enjoy!
