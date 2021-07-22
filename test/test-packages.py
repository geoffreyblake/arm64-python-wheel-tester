#!/usr/bin/env python3

import re
import os
import json
import time
import yaml
import subprocess
import multiprocessing
from datetime import datetime
from collections import defaultdict

def main():
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    with open('packages.yaml') as f:
        packages = yaml.safe_load(f.read())

    def get_test_set():
        for package in packages['packages']:
            package_main_name = re.findall(r'([\S]+)', package['PIP_NAME'])[0]
            package_list = package['PIP_NAME']
            package['main_name'] = package_main_name
            py_script = package['PKG_TEST']
            for container in ['amazon-linux2', 'centos8', 'centos8-py38', 'focal']:
                yield (package_main_name, package_list, container, 'container-script.sh', py_script, container)
            if 'APT_NAME' in package:
                yield (package_main_name, package['APT_NAME'], 'focal', 'container-apt-test.sh', py_script, 'focal-apt')
            if 'YUM_NAME' in package:
                yield (package_main_name, package['YUM_NAME'], 'centos8', 'container-yum-test.sh', py_script, 'centos8-yum')

    with multiprocessing.Pool(processes=os.cpu_count(), initializer=do_test_initializer) as pool:
        results_list = pool.map(do_test_lambda, get_test_set())

    results = defaultdict(dict)
    for result in results_list:
        results[result['wheel']][result['test-name']] = result
        del result['wheel']
        del result['test-name']


    subprocess.run('rm -rf work_pid*', shell=True)
    with open('results.json', 'w') as f:
        json.dump(results, f, indent=2)
    subprocess.run(['xz', 'results.json'], check=True)
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.rename('results.json.xz', f'results-{now}.json.xz')

    # Also generate an html report of the results
    subprocess.run(f'python3 process-results.py -o report-{now}.html --by-test results-{now}.json.xz', shell=True)

    # chmod the results so that the host can remove the file when cleaning up
    subprocess.run('chmod ugo+rw results* report*', shell=True, check=True)

process_work_dir = ''
def do_test_initializer():
    global process_work_dir
    process_work_dir = "work_pid_%d" % os.getpid()
    os.mkdir(process_work_dir)
    subprocess.run(f'cp container-* {process_work_dir}/', shell=True)

def do_test_lambda(x):
    return do_test(*x)
def do_test(package_main_name, package_list, container, test_sh_script, test_py_script, test_name):
    result = {
        'test-passed': False,
        'build-required': False,
        'binary-wheel': False,
        'slow-install': False,
        'wheel': package_main_name,
        'test-name': test_name,
    }
    with open(f'{process_work_dir}/test-script.py', 'w') as f:
        f.write(test_py_script)
    wd = os.environ['WORK_PATH']
    start = time.time()
    proc = subprocess.run(['docker', 'run',
            '--interactive', '--rm', '-v', f'{wd}/{process_work_dir}:/io',
            '--env', f'PACKAGE_LIST={package_list}',
            container,
            'bash', f'/io/{test_sh_script}'],
            encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    if time.time() - start > 60:
        result['slow-install'] = True

    if proc.returncode == 0:
        result['test-passed'] = True

    if re.search(r'Building wheel for', proc.stdout) is not None:
        result['build-required'] = True

    if re.search(f'Downloading {package_main_name}[^\n]*aarch64[^\n]*whl', proc.stdout) is not None:
        result['binary-wheel'] = True

    result['output'] = proc.stdout

    outcome = "passed" if result['test-passed'] else "failed"
    print(f"Package {package_main_name} on {test_name} {outcome}.")

    return result


if __name__ == '__main__':
    main()
