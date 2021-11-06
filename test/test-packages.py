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

SLOW_INSTALL_TIME = 60
TIMEOUT = 180

def main():
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    with open('packages.yaml') as f:
        packages = yaml.safe_load(f.read())

    def get_test_set():
        installers = {
            'CONDA_NAME': 'container-conda-test.sh', 
            'PIP_NAME': 'container-script.sh', 
            'APT_NAME': 'container-apt-test.sh', 
            'YUM_NAME': 'container-yum-test.sh'
        } 
        for package in packages['packages']:
            for install_type in installers.keys():
                if install_type not in package: 
                    continue
                package_main_name = re.findall(r'([\S]+)', package['PKG_NAME'])[0]
                package_list = package[install_type]
                package['main_name'] = package_main_name
                py_script = package['PKG_TEST']
                if install_type == 'APT_NAME':
                    yield (package_main_name, package_list, 'focal', installers[install_type], py_script, 'focal-apt', install_type)
                elif install_type == 'YUM_NAME':
                    yield (package_main_name, package_list, 'centos8', installers[install_type], py_script, 'centos8-yum', install_type)
                else:
                    for container in ['amazon-linux2', 'centos8', 'centos8-py38', 'focal']:
                        test_name = container
                        if install_type == 'CONDA_NAME':
                            test_name += '-conda'
                        yield (package_main_name, package_list, container, installers[install_type], py_script, test_name, install_type)

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
def do_test(package_main_name, package_list, container, test_sh_script, test_py_script, test_name, install_type):
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
            container,
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
            print(f"{install_type[:-5]}: Package {package_main_name} on {test_name} TIMED OUT!!")
            break
        time.sleep(1)

    proc = subprocess.run(['docker', 'container', 'inspect', '-f', '{{ .State.ExitCode }}', container_id],
            encoding='utf-8', stdout=subprocess.PIPE)
    return_code = int(proc.stdout.strip())
    proc = subprocess.run(['docker', 'logs', container_id],
            encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    print(f"{install_type[:-5]}: Package {package_main_name} on {test_name} {outcome}.")

    subprocess.run(['docker', 'container', 'rm', container_id],
            encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return result


if __name__ == '__main__':
    main()
