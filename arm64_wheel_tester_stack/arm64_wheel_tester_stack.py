from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
)
from constructs import Construct

import boto3
import dateutil.parser
import os

# Simplistic way to manage some secrets via the environment
# from the developer's laptop/workstation.
PROFILE = os.environ['AWS_PROFILE']
KEY_NAME = os.environ['AWS_KEY_NAME']
try:
    AWS_PREFIX_LIST = os.environ['AWS_PREFIX_LIST']
except:
    AWS_PREFIX_LIST = None
AWS_ACCESS_KEY_ID = os.environ['AWS_ACCESS_KEY_ID']
AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
AWS_SESSION_TOKEN = os.environ['AWS_SESSION_TOKEN']

REGIONS = ['us-east-1']
UBUNTU = 'ubuntu'
CENTOS = 'centos'
AL2 = 'AL2'


AMI_FILTERS = {
    'ubuntu': { 'Owner': '099720109477',
                'name': 'ubuntu/images/hvm-ssd-gp3/ubuntu-noble*'
              }
}

def getLatestAmi(arch: str, name_filter: str, owner: str):
    ami_map = {}
    for region in REGIONS:
        session = boto3.session.Session(profile_name=PROFILE, region_name=region, 
                        aws_access_key_id=AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                        aws_session_token=AWS_SESSION_TOKEN)
        client = session.client("ec2")
        resp = client.describe_images(ExecutableUsers=["all"],
            Filters=[{'Name': 'architecture', 'Values': [arch]},
                     {'Name': 'name', 'Values': [name_filter]}],
            Owners=[owner]
            )
        images = resp["Images"]
        images = sorted(images, key=lambda image: dateutil.parser.parse(image['CreationDate']))
        ami_map[region] = images[0]['ImageId']

    return ec2.MachineImage.generic_linux(ami_map)


def getLatestUbuntuAmi():
    return getLatestAmi('arm64', AMI_FILTERS[UBUNTU]['name'], AMI_FILTERS[UBUNTU]['Owner'])


class Arm64WheelTesterStack(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        vpc = ec2.Vpc(self, "Github-Selfhost-vpc",
                      nat_gateways = 0,
                      enable_dns_hostnames = True,
                      enable_dns_support = True,
                      subnet_configuration=[ec2.SubnetConfiguration(name="selfhost_public", subnet_type=ec2.SubnetType.PUBLIC)]
                      )

        ubuntu = getLatestUbuntuAmi()

        instances = []

        user_data = ec2.UserData.for_linux()
        user_data.add_commands("apt-get update -y",
                                     "apt-get upgrade -y",
                                     "apt-get install -y curl software-properties-common",
                                     "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -",
                                     "add-apt-repository "
                                     "'deb [arch=arm64] https://download.docker.com/linux/ubuntu noble stable'",
                                     "apt-get update -y",
                                     "apt-get install -y docker-ce docker-ce-cli containerd.io",
                                     "systemctl start docker")
        instance_wheel_tester = ec2.Instance(self, "wheel-tester",
            instance_type=ec2.InstanceType("m8g.2xlarge"),
            machine_image=ubuntu,
            vpc=vpc,
            key_name=KEY_NAME,
            block_devices=[ec2.BlockDevice(device_name='/dev/sda1', volume=ec2.BlockDeviceVolume.ebs(128))],
            user_data=user_data)
        instance_wheel_tester.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
        )
        instances.append(instance_wheel_tester)

        for instance in instances:
            instance.connections.allow_from_any_ipv4(ec2.Port.tcp(443), 'Allow inbound HTTPS connections')
            if AWS_PREFIX_LIST:
                instance.connections.allow_from(ec2.Peer.prefix_list(AWS_PREFIX_LIST), ec2.Port.tcp(22), 'Allow inbound SSH connections from trusted sources')
