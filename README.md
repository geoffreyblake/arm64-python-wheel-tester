# Arm64 python wheels tester
This is a simple project to run wheels in a docker environment on 4k and 64k page-size systems to detect possible incompatibilities
in upstream wheels on Arm64 systems.  It uses github actions and self-hosted runners to guarantee the system configurations we need.

A report of the test status is generated daily and posted [here](https://geoffreyblake.github.io/arm64-python-wheel-tester/).

This project could also be repurposed for other interpreted languages that contain native bindings, such as Ruby Gems.

# Using the CDK to generate self-hosted Graviton2 runners for testing Wheels!

This projects uses the AWS CDK to stand up some infra-structure in AWS for testing
python wheels built for Arm64 on Graviton2 processors.  The CDK scripts will allow one to
stand up an m6g.large runner and attempts to install with the necessary dependencies for github runners.
If the installation fails, just follow the steps from github to manually install the runners.

To use:

```
$ python3 -m venv .env
$ source .env/bin/activate
$ pip install -r requirements.txt

# Create a file with your AWS credentials and github tokens called .aws_creds
$ source ./.aws_creds
$ npm install -g aws-cdk
$ cdk synth --profile=<profile>
$ cdk deploy
```

Then go to:
- [About self-hosted github runners](https://docs.github.com/en/actions/hosting-your-own-runners/about-self-hosted-runners)
- [Adding self-hosted github runners](https://docs.github.com/en/actions/hosting-your-own-runners/adding-self-hosted-runners)
- [Using self-hosted github runners](https://docs.github.com/en/actions/hosting-your-own-runners/using-self-hosted-runners-in-a-workflow)

To learn about the runners and how to use/trouble-shoot them.


## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation
