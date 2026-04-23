#!/usr/bin/env python3

import aws_cdk as cdk

from arm64_wheel_tester_stack.arm64_wheel_tester_stack import Arm64WheelTesterStack

app = cdk.App()

Arm64WheelTesterStack(app, "arm64-github-testers", env=cdk.Environment(region='us-east-1'))

app.synth()
