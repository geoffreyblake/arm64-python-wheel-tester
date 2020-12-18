#!/usr/bin/env python3

from aws_cdk import core

from arm64_wheel_tester_stack.arm64_wheel_tester_stack import Arm64WheelTesterStack

app = core.App()

Arm64WheelTesterStack(app, "arm64-github-testers", env={'region': 'us-east-1'})

app.synth()
