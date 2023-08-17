#!/usr/bin/env python3

import re
import glob
import json
import lzma
import math
import argparse
import requests
from functools import reduce
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
from html import escape as html_escape

def main():
    parser = argparse.ArgumentParser(description="Parse result files and render an HTML page with a status summary")
    parser.add_argument('resultfiles', type=str, nargs='+', metavar='results.json', help='path to a result file')
    parser.add_argument('--ignore', type=str, action='append', help='Ignore tests with the specified name; can be used more than once.', default=[])
    parser.add_argument('--by-test', action='store_true', help="print results by test (distro)")
    parser.add_argument('-o', '--output-file', type=str, help="file name to write report")
    parser.add_argument('--compare-weekday-num', type=int, help="integer weekday number to hinge the summary report on", default=None)

    args = parser.parse_args()
    if args.by_test:
        html = print_table_by_distro_report(args.resultfiles, args.ignore, args.compare_weekday_num)
    else:
        html = print_table_report(args.resultfiles, args.ignore)
    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(html)
    else:
        print(html)

def get_wheels_with_result(wheel_dict, key='test-passed', result=False, ignore_tests=[]):
    wheels = set()
    for wheel_name, wheel_results in wheel_dict.items():
        if wheel_name in ignore_tests:
            continue
        for test_name, test_results in wheel_results.items():
            if test_results[key] == result:
                wheels.add(wheel_name)
    return list(wheels)

def get_failing_tests(wheel_dict, ignore_tests=[]):
    return get_wheels_with_result(wheel_dict, 'test-passed', False, ignore_tests)

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

def get_package_name_class(test_name):
    if 'conda' in test_name:
        return 'package-conda'
    elif 'apt' in test_name:
        return 'package-os'
    elif 'yum' in test_name:
        return 'package-os'
    else:
        return 'package-pip'

def get_distribution_name(test_name):
    distros = ["amazon-linux2", "centos8", "focal", "jammy"]
    for distro in distros:
        if distro in test_name:
            return distro
    return None

def get_package_manager_name(test_name):
    names = ['yum', 'apt', 'conda']
    for name in names:
        if name in test_name:
            return name
    return 'pip'


class TestResultFile():
    def __init__(self, fname):
        self.fname = fname
        self.content = None
        self.date = None
        self.wheels = {}

    def add_inferred_meta_data(self):
        for wheel, wheel_dict in self.content.items():
            passed_by_distro = defaultdict(lambda: False)
            self.wheels[wheel] = {}
            self.wheels[wheel]['results'] = wheel_dict
            for test_name, test_name_results in wheel_dict.items():
                distribution = get_distribution_name(test_name)
                test_name_results['distribution'] = distribution
                test_name_results['package_manager'] = get_package_manager_name(test_name)
                passed_by_distro[distribution] |= test_name_results['test-passed']
            self.wheels[wheel]['passed-by-disribution'] = passed_by_distro
            self.wheels[wheel]['each-distribution-has-passing-option'] = len(list(filter(lambda x: not x, passed_by_distro.values()))) == 0

def get_wheel_ranks():
    url = 'https://hugovk.github.io/top-pypi-packages/top-pypi-packages-30-days.min.json'
    try:
        r = requests.get(url)
    except requests.RequestsError:
        print('failed to load top pypi packages list')
        return []

    try:
        packages = r.json()['rows']
        # the list should be sorted already, but lets not assume that
        packages = sorted(packages, key=lambda x: x['download_count'], reverse=True)
        packages = [package['project'] for package in packages]
        return packages
    except KeyError:
        print('unable to parse top pypi packages list; the format may have changed')
        return []

def print_table_by_distro_report(test_results_fname_list, ignore_tests=[], compare_weekday_num=None):

    test_results_list = []
    for fname in test_results_fname_list:
        test_result_file = TestResultFile(fname)
        if re.search(r'\.xz$', fname) is not None:
            with lzma.open(fname) as f:
                test_result_file.content = json.load(f)
        else:
            with open(fname) as f:
                test_result_file.content = json.load(f)

        mo = re.search('[^/]-([0-9\-_]+).json.xz', fname)
        if mo is not None:
            test_result_file.date = datetime.strptime(mo.group(1), "%Y-%m-%d_%H-%M-%S")
        test_result_file.add_inferred_meta_data()
        test_results_list.append(test_result_file)

    # Sort the test result files by date because code that follows assumes this order.
    test_results_list = sorted(test_results_list, key=lambda x: x.date, reverse=True)

    # get a sorted list of all the wheel names
    wheel_name_set = set()
    # get a sorted list of all the test_names (distros, plus extra, e.g. centos-python38)
    all_test_names = set()
    for test_result in test_results_list:
        wheel_name_set.update(test_result.content.keys())
        for wheel, wheel_dict in test_result.content.items():
            for test_name, test_name_results in wheel_dict.items():
                if test_name not in ignore_tests:
                    all_test_names.add(test_name)
    wheel_name_set = sorted(list(wheel_name_set), key=str.lower)
    all_test_names = sorted(list(all_test_names))

    # get the wheel popularity ranking
    wheel_ranks = get_wheel_ranks()
    leading_zeros = math.floor(math.log10(len(wheel_ranks))) + 1
    wheel_rank_format = f'{{n:0{leading_zeros}d}}'
    print(wheel_rank_format)

    html = []
    html.append(HTML_HEADER)
    pretty_date = test_results_list[0].date.strftime("%B %d, %Y")
    html.append(f'<h1>Python Wheels on aarch64 test results from {pretty_date}</h1>')
    html.append('<section class="summary">')

    # Find the result file to compare against for the top-level summary.
    reference_test_file = None
    if type(compare_weekday_num) is int:
        reference_date = test_results_list[0].date
        reference_date = reference_date.replace(hour=23, minute=59)
        reference_date = reference_date - timedelta(days=reference_date.weekday()) + timedelta(days=compare_weekday_num)
        current_weekday = test_results_list[0].date.weekday()
        if current_weekday <= compare_weekday_num:
            reference_date -= timedelta(days=7)
        for test_result_file in test_results_list:
            if test_result_file.date < reference_date:
                reference_test_file = test_result_file
                break
        summary_table = [['date', 'number of wheels', 'all tests passed', 'some tests failed', 'each dist has passing option']]
        for test_result_file in [reference_test_file, test_results_list[0]]:
            count = len(test_result_file.content)
            failures = len(get_failing_tests(test_result_file.content))
            all_passing = count - failures
            date = test_result_file.date.strftime("%A, %B %d, %Y")
            passing_options = len(list(filter(lambda wheel: wheel['each-distribution-has-passing-option'], test_result_file.wheels.values())))
            summary_table.append([date, count, all_passing, failures, passing_options])

        html.append('<table class="summary">')
        for index in range(len(summary_table[0])):
            html.append('<tr>')
            for column_index, column_data in enumerate(summary_table):
                element = 'th' if column_index == 0 else 'td'
                html.append(f'<{element}>{column_data[index]}</{element}>')
            if summary_table[0][index] != 'date':
                difference = summary_table[2][index] - summary_table[1][index]
                plus = '+' if difference >= 0 else ''
                html.append(f'<td>{plus}{difference}</td>')
            else:
                html.append('<td></td>')
            html.append('</tr>')
        html.append('</table>')


    html.append('<p>The table shows test results from the current test run and differences, if any, with previous runs.')
    html.append('When differences exist, the first test report exhibting the difference is shown. The current test result')
    html.append('is always shown, regardless of whether there is any difference.</p>')
    html.append('</section>')
    html.append('<section>')
    html.append('<table class="python-wheel-report" id="python-wheel-report">')
    html.append('<thead><tr>')
    html.append('<th></th>')
    html.append('<th>rank by downloads on pypi</th>')
    html.append('<th>at least one passing option per distribution?</th>')
    for test_name in all_test_names:
        html.append(f'<th class="test-column {get_package_name_class(test_name)}">{test_name}</th>')
    html.append('</thead></tr><tbody>')

    def date_of_last_passing_html(wheel, test_name):
        if test_name == 'each-distribution-has-passing-option':
            passing_lambda = lambda tf: tf.wheels[wheel][test_name]
        else:
            passing_lambda = lambda tf: tf.content[wheel][test_name]['test-passed']
        last_passing = None
        for test_result_file in test_results_list[1:]:
            try:
                if passing_lambda(test_result_file):
                    last_passing = test_result_file.date
                    break
            except KeyError:
                continue
        if last_passing:
            last_passing = last_passing.strftime("%B %d, %Y")
            return f'<br /><span class="file-indicator">last passed on {last_passing}</span>'
        else:
            return ''

    test_result_file = test_results_list[0]
    # Iterate over the sorted list of wheel names
    for i, wheel in enumerate(wheel_name_set):
        odd_even = 'even' if (i+1) % 2 == 0 else 'odd'
        different = False
        different_class = 'different' if different else ''
        if different:
            pretty_date = test_result_file.date.strftime("%B %d, %Y")
            file_indicator = f'<br /><span class="file-indicator">{pretty_date}</span>'
        else:
            file_indicator = ''
        html.append(f'<tr class="wheel-line {odd_even}">')
        html.append(f'<td class="wheel-name {different_class}">{wheel}{file_indicator}</td>')
        try:
            wheel_rank = wheel_rank_format.format(n=wheel_ranks.index(wheel) + 1)
        except (IndexError, ValueError):
            wheel_rank = '~'
        html.append(f'<td class="">{wheel_rank}</td>')
        html.append('<td class="">')
        if wheel in test_result_file.wheels:
            distro_passing = test_result_file.wheels[wheel]['each-distribution-has-passing-option']
            if distro_passing:
                html.append(make_badge(classes=['passed'], text='yes'))
            else:
                html.append(make_badge(classes=['failed'], text='no'))
                html.append(date_of_last_passing_html(wheel, 'each-distribution-has-passing-option'))
        html.append('</td>')
        for test_name in all_test_names:
            html.append(f'<td class="test-column {get_package_name_class(test_name)}">')
            if wheel in test_result_file.content and test_name in test_result_file.content[wheel]:
                result = test_result_file.content[wheel][test_name]
                show_output = False
                if result['test-passed']:
                    html.append(make_badge(classes=['passed'], text='passed'))
                else:
                    html.append(make_badge(classes=['failed'], text='failed'))
                    show_output = True
                if result['build-required']:
                    html.append(make_badge(classes=['warning'], text='build required'))
                if result['slow-install']:
                    html.append(make_badge(classes=['warning'], text='slow install'))
                if 'timeout' in result and result['timeout']:
                    html.append(make_badge(classes=['failed'], text='timed out'))
                    show_output = True

                if show_output:
                    html.append(date_of_last_passing_html(wheel, test_name))
                    output_id = html_escape(f"output_{test_result_file.date}_{wheel}_{test_name}")
                    output_html = html_escape(result['output'])
                    html.append(f'<input type="checkbox" id="{output_id}" class="output-toggle" />')
                    html.append(f'<label for="{output_id}" class="output-toggle">Toggle Output</label>')
                    html.append(f'<pre class="output-content">{output_html}</pre>')

            html.append('</td>')

        html.append('</tr>')

    html.append('</tbody></table>')
    html.append('</section>')
    html.append(HTML_FOOTER)
    html = '\n'.join(html)
    return html

HTML_HEADER = '''
<!doctype html>
<html>
<head>
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.css" />
<script src="https://code.jquery.com/jquery-3.7.0.slim.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.js"></script>
<script type="text/javascript">
    $(document).ready(function() {
            $('#python-wheel-report').DataTable({
                paginate: false
            });
        });
</script>
<style type="text/css">

h1 {
    text-align: center;
}

section.summary {
    margin: 0 auto;
    width: 900px;
    font-family: sans-serif;
}

section.summary table {
    margin: 0 auto;
    width: 700px;
    border-collapse: collapse;
}

section.summary th, section.summary td {
    border: solid 1px;
    margin: 0px;
    padding: 3px;
}

table.python-wheel-report {
    margin: 0 auto;
    width: 100%;
}

table.python-wheel-report td, table.python-wheel-report th {
    padding: 5px;
    border-width: 0px;
    margin: 5px;
    font-family: monospace;
    line-height: 1.6em;
    width: 14%;
    vertical-align: baseline;
}

table.python-wheel-report th {
    position:sticky;
    top:0px;
    background-color: white;
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


/* Styles for "Toggle Output" accordions */
input.output-toggle {
    display: none;
}
label.output-toggle {
    cursor: pointer;
}
input.output-toggle + label.output-toggle + pre.output-content {
    display: none;
}
input.output-toggle:checked + label.output-toggle + pre.output-content {
    display: block;
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
