#!/usr/bin/env python3

import re
import glob
import json
import lzma
import argparse
from functools import reduce
from collections import OrderedDict

def main():
    parser = argparse.ArgumentParser(description="Parse result files and render an HTML page with a status summary")
    parser.add_argument('resultfiles', type=str, nargs='+', metavar='results.json', help='path to a result file')
    parser.add_argument('--ignore', type=str, action='append', help='Ignore tests with the specified name; can be used more than once.')
    parser.add_argument('--by-test', action='store_true', help="print results by test (distro)")
    parser.add_argument('-o', '--output-file', type=str, help="file name to write report")

    args = parser.parse_args()
    if args.by_test:
        html = print_table_by_distro_report(args.resultfiles, args.ignore)
    else:
        html = print_table_report(args.resultfiles, args.ignore)
    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(html)
    else:
        print(html)

def get_tests_with_result(wheel_dict, key='test-passed', result=False, ignore_tests=[]):
    tests = []
    for test_name, test_results in wheel_dict.items():
        if test_name in ignore_tests:
            continue
        if test_results[key] == result:
            tests.append(test_name)
    return tests

def get_failing_tests(wheel_dict, ignore_tests=[]):
    return get_tests_with_result(wheel_dict, 'test-passed', False, ignore_tests)

def get_build_required(wheel_dict, ignore_tests=[]):
    return get_tests_with_result(wheel_dict, 'build-required', True, ignore_tests)

def get_build_required(wheel_dict, ignore_tests=[]):
    return get_tests_with_result(wheel_dict, 'build-required', True, ignore_tests)

def print_report(all_wheels):
    passing = []
    failing = []
    for wheel, wheel_dict in all_wheels.items():
        failed_tests = get_failing_tests(wheel_dict)
        if len(failed_tests) == 0:
            passing.append((wheel, wheel_dict))
        else:
            failing.append((wheel, wheel_dict))
    html = []
    html.append(f'<h1>Passing - {len(passing)}</h1>')
    html.append('<ul>')
    for wheel, wheel_dict in passing:
        html.append(f'<li>{wheel}</li>')
    html.append('</ul>')

    html.append(f'<h1>Failing - {len(failing)}</h1>')
    html.append('<ul>')
    for wheel, wheel_dict in failing:
        html.append(f'<li>{wheel}</li>')
    html.append('</ul>')

    html = '\n'.join(html)
    return html

def get_wheel_report_cell(wheel, wheel_dict, ignore_tests):
    failing = get_failing_tests(wheel_dict, ignore_tests=ignore_tests)
    build_required = get_build_required(wheel_dict, ignore_tests=ignore_tests)
    slow_install = get_tests_with_result(wheel_dict, 'slow-install', True, ignore_tests=ignore_tests)
    badges = set()

    cell_text = []
    cell_text.append('<div>')
    if len(failing) == 0 and len(build_required) == 0 and len(slow_install) == 0:
        cell_text.append('<span class="perfect-score badge">perfect score</span> ')
        badges.add('perfect-score')
    elif len(failing) == 0:
        cell_text.append('<span class="all-passed badge">all-passed</span> ')
        badges.add('all-passed')
    if len(build_required) > 0:
        cell_text.append('<span class="build-required badge">build required</span> ')
        badges.add('build-required')
    if len(slow_install) > 0:
        cell_text.append('<span class="slow-install badge">slow-install</span> ')
        badges.add('slow-install')
    for test_name in failing:
        cell_text.append(f'<span class="test-name badge">{test_name}</span>')
        badges.add(test_name)

    cell_text.append('</div>')
    return ('\n'.join(cell_text), badges)

def load_result_files(test_results_fname_list):
    for fname in test_results_fname_list:
        if re.search(r'\.xz$', fname) is not None:
            with lzma.open(fname) as f:
                yield json.load(f), fname
        else:
            with open(fname) as f:
                yield json.load(f), fname


def print_table_report(test_results_fname_list, ignore_tests=[]):
    test_results_list = []
    if ignore_tests is None:
        ignore_tests = []

    all_keys = set()
    for test_results, fname in load_result_files(test_results_fname_list):
        test_results_list.append(test_results)
        all_keys.update(test_results.keys())
    all_keys = sorted(list(all_keys), key=str.lower)

    html = []
    html.append(HTML_HEADER)
    html.append('<table class="python-wheel-report">')
    html.append('<tr>')
    html.append('<th></th>')
    for i, test_results in enumerate(test_results_list):
        html.append(f'<th>{test_results_fname_list[i]}</th>')
    html.append('</tr>')
    for i, wheel in enumerate(all_keys):
        test_results_cache = {}
        for test_results_i, test_results in enumerate(test_results_list):
            if wheel in test_results:
                wheel_dict = test_results[wheel]
                test_results_cache[test_results_i] = get_wheel_report_cell(wheel, wheel_dict, ignore_tests)
        # check to see if the sets returned as item index 1 are all the same
        badge_set = None
        wheel_differences = False
        for s in map(lambda x: x[1][1], test_results_cache.items()):
            if badge_set is None:
                badge_set = s
            elif badge_set != s:
                wheel_differences = True
                break
        wheel_differences = 'different' if wheel_differences else ''
        odd_even = 'even' if (i+1) % 2 == 0 else 'odd'
        html.append(f'<tr class="wheel-line {odd_even}">')
        html.append(f'<td class="wheel-name {wheel_differences}">{wheel}</td>')
        for test_results_i, test_results in enumerate(test_results_list):
            html.append('<td class="wheel-report">')
            if wheel in test_results:
                html.append(test_results_cache[test_results_i][0])
            html.append('</td>')
        html.append('</tr>')
    html.append('</table>')
    html.append(HTML_FOOTER)
    html = '\n'.join(html)
    return html


def make_badge(classes=[], text=""):
    classes.append('badge')
    classes = " ".join(classes)
    return f'<span class="{classes}">{text}</span>'

def print_table_by_distro_report(test_results_fname_list, ignore_tests=[]):
    # TODO: add support for multipile result files displayed in tabs
    test_results_list = []
    for fname in test_results_fname_list:
        if re.search(r'\.xz$', fname) is not None:
            with lzma.open(fname) as f:
                test_results_list.append(json.load(f))
        else:
            with open(fname) as f:
                test_results_list.append(json.load(f))

    # get a sorted list of all the wheel names
    wheel_name_set = set()
    # get a sorted list of all the test_names (distros, plus extra, e.g. centos-python38)
    all_test_names = set()
    for test_result in test_results_list:
        wheel_name_set.update(test_result.keys())
        for wheel, wheel_dict in test_result.items():
            for test_name, test_name_results in wheel_dict.items():
                all_test_names.add(test_name)
    wheel_name_set = sorted(list(wheel_name_set), key=str.lower)
    all_test_names = sorted(list(all_test_names))

    html = []
    html.append(HTML_HEADER)
    html.append(f'<h1>{test_results_fname_list[0]}</h1>')
    html.append('<table class="python-wheel-report">')
    html.append('<tr>')
    html.append('<th></th>')
    for test_name in all_test_names:
        html.append(f'<th>{test_name}</th>')
    html.append('</tr>')
    for i, wheel in enumerate(wheel_name_set):
        # determine if any of the test files have different results
        different = False
        for test_name in all_test_names:
            b = None
            for a in test_results_list:
                try:
                    a = a[wheel][test_name]
                except KeyError:
                    continue
                t = (a['test-passed'], a['build-required'], a['slow-install'])
                if b is None:
                    b = t
                elif b != t:
                    different = True
                    break
            if different:
                break

        odd_even = 'even' if (i+1) % 2 == 0 else 'odd'
        different_class = 'different' if different else ''
        for test_result_index, test_results in enumerate(test_results_list):
            if different:
                file_indicator = f'<br /><span class="file-indicator">{test_results_fname_list[test_result_index]}</span>'
            else:
                file_indicator = ''
            html.append(f'<tr class="wheel-line {odd_even}">')
            html.append(f'<td class="wheel-name {different_class}">{wheel}{file_indicator}</td>')
            for test_name in all_test_names:
                html.append('<td class="">')
                if wheel in test_results and test_name in test_results[wheel]:
                    result = test_results[wheel][test_name]
                    if result['test-passed']:
                        html.append(make_badge(classes=['passed'], text='passed'))
                    else:
                        html.append(make_badge(classes=['failed'], text='failed'))
                    if result['build-required']:
                        html.append(make_badge(classes=['warning'], text='build required'))
                    if result['slow-install']:
                        html.append(make_badge(classes=['warning'], text='slow install'))
                    if 'timeout' in result and result['timeout']:
                        html.append(make_badge(classes=['failed'], text='timed out'))

                html.append('</td>')

            html.append('</tr>')
            if not different:
                break

    html.append('</table>')
    html.append(HTML_FOOTER)
    html = '\n'.join(html)
    return html

HTML_HEADER = '''
<!doctype html>
<html>
<head>
<style type="text/css">

table.python-wheel-report {
    margin: 0 auto;
    width: 960px;
}

table.python-wheel-report td, table.python-wheel-report th {
    padding: 5px;
    border-width: 0px;
    margin: 5px;
    font-family: monospace;
    line-height: 1.6em;
    width: 14%;
}

table.python-wheel-report span.perfect-score {
    color: white;
/* Permalink - use to edit and share this gradient: https://colorzilla.com/gradient-editor/#bfd255+0,8eb92a+50,72aa00+51,9ecb2d+100;Green+Gloss */
background: #bfd255; /* Old browsers */
background: linear-gradient(to bottom,  #bfd255 0%,#8eb92a 50%,#72aa00 51%,#9ecb2d 100%);
}

table.python-wheel-report span.test-name, span.failed {
    color: white;
/* Permalink - use to edit and share this gradient: https://colorzilla.com/gradient-editor/#f85032+0,f16f5c+50,f6290c+51,f02f17+71,e73827+100;Red+Gloss+%231 */
background: #f85032; /* Old browsers */
background: linear-gradient(to bottom,  #f85032 0%,#f16f5c 50%,#f6290c 51%,#f02f17 71%,#e73827 100%);
}

table.python-wheel-report span.all-passed, span.passed {
    color: white;
/* Permalink - use to edit and share this gradient: https://colorzilla.com/gradient-editor/#bfd255+0,8eb92a+50,72aa00+51,9ecb2d+100;Green+Gloss */
background: #bfd255; /* Old browsers */
background: linear-gradient(to bottom,  #bfd255 0%,#8eb92a 50%,#72aa00 51%,#9ecb2d 100%);
}

table.python-wheel-report span.build-required, span.warning {
    color: white;
/* Permalink - use to edit and share this gradient: https://colorzilla.com/gradient-editor/#ffd65e+0,febf04+100;Yellow+3D+%232 */
background: #ffd65e; /* Old browsers */
background: linear-gradient(to bottom,  #ffd65e 0%,#febf04 100%);
}

table.python-wheel-report span.slow-install {
    color: white;
/* Permalink - use to edit and share this gradient: https://colorzilla.com/gradient-editor/#ffd65e+0,febf04+100;Yellow+3D+%232 */
background: #ffd65e; /* Old browsers */
background: linear-gradient(to bottom,  #ffd65e 0%,#febf04 100%);
}


table.python-wheel-report span.badge {
    border-radius: 4px;
    margin: 3px;
    padding: 2px;
    white-space: nowrap;
}
table.python-wheel-report span.file-indicator {
    font-size: 0.5em;
}


table.python-wheel-report tr.odd {
    background-color: #f1f1f1;
}

table.python-wheel-report td.wheel-name.different {
    background: #d1ffd9;
    font-style: italic;
}



</style>
</head>
<body>
'''

HTML_FOOTER = '''
</body>
</html>
'''

if __name__ == '__main__':
    main()
