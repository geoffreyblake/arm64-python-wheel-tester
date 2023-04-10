#!/usr/bin/env python3

import re
import os
import json
import time
import yaml
import argparse
import importlib
import itertools
import subprocess
import multiprocessing
from datetime import datetime
from collections import defaultdict

process_results = importlib.import_module("process-results")
generate_website = importlib.import_module("generate-website")

SLOW_INSTALL_TIME = 60
TIMEOUT = 180

def main():
    parser = argparse.ArgumentParser(description="Run wheel tests")
    parser.add_argument('--token', type=str, help="Github API token")
    parser.add_argument('--ignore', type=str, action='append', help='Ignore tests with the specified name; can be used more than once.', default=[])
    parser.add_argument('--container', type=str, nargs='*', help='Specify which containers to test')
    args = parser.parse_args()

    # change working directory the path of this script
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    with open('packages.yaml') as f:
        packages = yaml.safe_load(f.read())

    def get_test_set():
        package_managers = {
            'CONDA': 'container-conda-test.sh',
            'PIP': 'container-script.sh',
            'APT': 'container-apt-test.sh',
            'YUM': 'container-yum-test.sh',
        }
        containers = {
            'amazon-linux2': ['PIP', 'CONDA'],
            'focal': ['PIP', 'APT', 'CONDA'],
            'jammy': ['PIP', 'APT'],
            'amazon-linux2-py38': ['PIP'],
            'amazon-linux2023': ['PIP', 'YUM'],
        }
        if args.container is not None and len(args.container) > 0:
            test_containers = args.container
        else:
            test_containers = containers.keys()
        # this is three nested loops in one
        for package, package_manager, container in itertools.product(packages['packages'], package_managers.keys(), test_containers):
            package_list_key = f'{package_manager}_NAME'
            if package_list_key not in package or package_manager not in containers[container]:
                continue
            package_main_name = re.findall(r'([\S]+)', package['PKG_NAME'])[0]
            package_list = package[package_list_key]
            package['main_name'] = package_main_name
            py_script = package['PKG_TEST']
            # to preserve compatibility in the result json files, don't label the pip tests in the test name
            if package_manager == 'PIP':
                test_name = container
            else:
                test_name = f'{container}-{package_manager.lower()}'
            test_shell_script = package_managers[package_manager]
            yield (package_main_name, package_list, container, test_shell_script, py_script, test_name, package_manager)

    results_list = []
    with multiprocessing.Pool(processes=os.cpu_count(), initializer=do_test_initializer) as pool:
        for result in pool.imap_unordered(do_test_lambda, get_test_set()):
            results_list.append(result)

    # cleanup subprocess work directories
    subprocess.run('rm -rf work_pid*', shell=True)

    results = defaultdict(dict)
    for result in results_list:
        results[result['wheel']][result['test-name']] = result
        del result['wheel']
        del result['test-name']

    output_dir = 'results'
    try:
        os.mkdir(output_dir)
    except FileExistsError:
        pass
    with open(f'{output_dir}/results.json', 'w') as f:
        json.dump(results, f, indent=2)
    subprocess.run(['xz', 'results.json'], check=True, cwd=output_dir)
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    new_results_file = f'{output_dir}/results-{now}.json.xz'
    os.rename(f'{output_dir}/results.json.xz', new_results_file)

    print("process results...")
    # Also generate an html report of the results
    html = process_results.print_table_by_distro_report([new_results_file], ignore_tests=args.ignore)
    with open(f'{output_dir}/report-{now}.html', 'w') as f:
        f.write(html)

    # Run the GitHub pages generator
    print("generate the website...")
    generate_website.generate_website(output_dir='build',
            new_results=new_results_file,
            github_token=args.token,
            days_ago_list=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 21],
            compare_weekday_num=3,
            ignore_tests=args.ignore)


process_work_dir = ''
def do_test_initializer():
    global process_work_dir
    process_work_dir = "work_pid_%d" % os.getpid()
    os.mkdir(process_work_dir)
    subprocess.run(f'cp container-* {process_work_dir}/', shell=True)

def do_test_lambda(x):
    return do_test(*x)
def do_test(package_main_name, package_list, container, test_sh_script, test_py_script, test_name, package_manager):
    result = {
        'test-passed': False,
        'build-required': False,
        'binary-wheel': False,
        'slow-install': False,
        'timeout': False,
        'wheel': package_main_name,
        'test-name': test_name,
    }
    with open(f'{process_work_dir}/test-script.py', 'w') as f:
        f.write(test_py_script)
    wd = os.environ['WORK_PATH']
    start = time.time()
    proc = subprocess.run(['docker', 'run',
            '-d', '-v', f'{wd}/{process_work_dir}:/io',
            '--env', f'PACKAGE_LIST={package_list}',
            f'wheel-tester/{container}',
            'bash', f'/io/{test_sh_script}'],
            encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    container_id = proc.stdout.strip()

    # wait until the timeout for the container to complete
    while True:
        proc = subprocess.run(['docker', 'container', 'inspect', '-f', '{{ .State.Running }}', container_id],
                encoding='utf-8', stdout=subprocess.PIPE)
        if proc.stdout.strip() != "true":
            break
        elif time.time() - start > TIMEOUT:
            result['timeout'] = True
            subprocess.run(['docker', 'stop', container_id])
            print(f"{package_manager}: Package {package_main_name} on {test_name} TIMED OUT!!")
            break
        time.sleep(1)

    proc = subprocess.run(['docker', 'container', 'inspect', '-f', '{{ .State.ExitCode }}', container_id],
            encoding='utf-8', stdout=subprocess.PIPE)
    return_code = int(proc.stdout.strip())
    proc = subprocess.run(['docker', 'logs', container_id],
            encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = proc.stdout

    if time.time() - start > SLOW_INSTALL_TIME:
        result['slow-install'] = True

    if return_code == 0:
        result['test-passed'] = True

    if re.search(r'Building wheel for', output) is not None:
        result['build-required'] = True

    if re.search(f'Downloading {package_main_name}[^\n]*aarch64[^\n]*whl', output) is not None:
        result['binary-wheel'] = True

    result['output'] = output

    outcome = "passed" if result['test-passed'] else "failed"
    print(f"{package_manager}: Package {package_main_name} on {test_name} {outcome}.")

    subprocess.run(['docker', 'container', 'rm', container_id],
            encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return result


if __name__ == '__main__':
    main()
