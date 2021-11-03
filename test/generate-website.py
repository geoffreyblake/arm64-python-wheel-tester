#!/usr/bin/env python3

import io
import os
import json
import zipfile
import argparse
import requests
import tempfile
import importlib
import subprocess
from datetime import datetime, timedelta

process_results = importlib.import_module("process-results")

def main():
    parser = argparse.ArgumentParser(description="Generate the static website")
    parser.add_argument('-o', '--output-dir', type=str, help="directory for the generated website", required=True)
    parser.add_argument('--repo', type=str, help="path to the source git repository", default=None)
    parser.add_argument('--website-branch', type=str, help="name of website branch", default=None)
    parser.add_argument('--new-results', type=str, help="result file to add to website", required=True)
    parser.add_argument('--compare-n-days-ago', type=int, help="number of days in the past to compare against", nargs='+')
    parser.add_argument('--github-token', type=str, help="github api token", required=True)
    parser.add_argument('--compare-weekday-num', type=int, help="integer weekday number to hinge the summary report on", default=None)

    args = parser.parse_args()

    generate_website(args.output_dir, args.new_results, args.github_token, args.compare_n_days_ago,
            repo_path=args.repo, website_branch=args.website_branch, compare_weekday_num=args.compare_weekday_num)

def generate_website(output_dir, new_results, github_token, days_ago_list=[], repo_path="/repo", website_branch="gh-pages",
        compare_weekday_num=None):
    # TODO: checkout the existing gh-pages and update it with a new report rather than replacing it completely
    # clone the repo to a temporary directory and checkout the website branch
    #webrepo = tempfile.mkdtemp()
    #subprocess.run(f'git clone --no-checkout -b {website_branch} {repo_path} {webrepo}', shell=True)

    # download results from previous run
    previous_results = fetch_previous_results(days_ago_list, github_token=github_token)

    results = [new_results]
    results.extend(previous_results)
    html = process_results.print_table_by_distro_report(results, compare_weekday_num=compare_weekday_num)

    try:
        os.mkdir(output_dir)
    except FileExistsError:
        pass
    with open(f'{output_dir}/index.html', 'w') as f:
        f.write(html)



def fetch_previous_results(days_ago_list, github_token):
    if len(days_ago_list) == 0:
        return []

    api_date_format = '%Y-%m-%dT%H:%M:%SZ'
    try:
        github_repo = os.environ['GITHUB_REPOSITORY']
        github_api_url = os.environ['GITHUB_API_URL']
    except KeyError:
        return []

    url = f'{github_api_url}/repos/{github_repo}/actions/artifacts'
    try:
        r = requests.get(url, headers={'Accept': 'application/vnd.github.v3+json'})
    except requests.RequestsError:
        print("failed to read from github api")
        return []

    response_data = r.json()
    days_ago_list = sorted(days_ago_list, reverse=True)
    artifacts = sorted(response_data['artifacts'], reverse=True, key=lambda x: datetime.strptime(x['created_at'], api_date_format))
    now = datetime.utcnow()
    results = []
    for artifact in artifacts:
        if len(days_ago_list) == 0:
            break
        created_at = datetime.strptime(artifact['created_at'], api_date_format)
        if now - timedelta(days=days_ago_list[-1]) > created_at:
            results.append(artifact)
            days_ago_list.pop()

    if len(results) == 0:
        return []

    result_fnames = []
    previous_results_dir = tempfile.mkdtemp()
    for previous_result in results:
        url = previous_result['archive_download_url']
        r = requests.get(url, headers={'Accept': 'application/vnd.github.v3+json', 'Authorization': f'Bearer {github_token}'})
        zf = zipfile.ZipFile(io.BytesIO(r.content))

        # find the first xz file
        for fname in zf.namelist():
            if fname[-3:] == '.xz':
                with zf.open(fname) as f:
                    result_fname = f'{previous_results_dir}/{fname}'
                    with open(result_fname, 'wb') as dest_f:
                        dest_f.write(f.read())
                    result_fnames.append(result_fname)
                break


    return result_fnames


if __name__ == '__main__':
    main()
