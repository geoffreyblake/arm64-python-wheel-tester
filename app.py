#!/usr/bin/env python3

from aws_cdk import core

from graviton2_wheel_tester_stack.graviton2_wheel_tester_stack import Graviton2WheelTesterStack

app = core.App()

Graviton2WheelTesterStack(app, "graviton2-github-testers", env={'region': 'us-east-1'})

app.synth()
