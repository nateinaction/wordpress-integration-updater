#!/usr/bin/env python

import jwt
import requests
import subprocess
import time

OWNER = 'worldpeaceio'
REPO = 'wordpress-integration'
DEV_BRANCH = 'develop'
PROD_BRANCH = 'master'


def check_dev_branch_status():
    """Check develop branch for CI status and most recent commit ID"""
    # This endpoint is still in beta so we need to pass a header
    headers = {'Accept': 'application/vnd.github.antiope-preview+json'}
    dev_branch_status_api = 'https://api.github.com/repos/{}/{}/commits/{}/check-runs'.format(OWNER, REPO, DEV_BRANCH)
    response = requests.get(dev_branch_status_api, headers=headers)
    response_json = response.json()
    run_status = response_json.get('check_runs')[0]
    return run_status['conclusion'], run_status['head_sha']


def get_prod_most_recent_commit_id():
    prod_branch_commit_api = 'https://api.github.com/repos/{}/{}/commits?sha={}'.format(OWNER, REPO, PROD_BRANCH)
    response = requests.get(prod_branch_commit_api)
    response_json = response.json()
    return response_json[0].get('sha')


def git_clone_checkout_and_push(repo_location, prod_branch, dev_branch, repo_directory=None):
    """Git clone a repo"""
    output = subprocess.run(['git', 'clone', '--depth', '1', '--branch', prod_branch, repo_location, repo_directory],
                            capture_output=True)
    pretty_out = output.stdout.decode('utf8')
    pretty_err = output.stderr.decode('utf8')

    # git pull origin develop
    output = subprocess.run(['git', 'pull', 'origin', dev_branch], cwd=repo_directory, capture_output=True)
    pretty_out += output.stdout.decode('utf8')
    pretty_err += output.stderr.decode('utf8')

    # git push origin master
    output = subprocess.run(['git', 'push', 'origin', prod_branch], cwd=repo_directory, capture_output=True)
    pretty_out += output.stdout.decode('utf8')
    pretty_err += output.stderr.decode('utf8')

    return pretty_out + pretty_err


def generate_jwt(app_key):
    github_app_id = '23151'
    payload = {
        'iat': int(time.time()),
        'exp': int(time.time() + (10 * 60)),
        'iss': github_app_id,
    }
    return jwt.encode(payload, app_key, algorithm='RS256')


def fetch_github_token(jwt):
    github_installation_id = '588987'
    url = 'https://api.github.com/app/installations/{}/access_tokens'.format(github_installation_id)
    headers = {
        'Authorization': 'Bearer {}'.format(jwt.decode('utf8')),
        'Accept': 'application/vnd.github.machine-man-preview+json',
    }
    response = requests.post(url, headers=headers)
    return response.json().get('token')


if __name__ == "__main__":
    """
    If develop branch is ahead of master and CI is passing then merge develop to master.
    """
    print('WordPress Integration Merge Master starting')

    dev_branch_state, dev_branch_commit_id = check_dev_branch_status()
    print('{} branch of {}/{} at commit ID {}'.format(DEV_BRANCH, OWNER, REPO, dev_branch_commit_id))

    prod_branch_commit_id = get_prod_most_recent_commit_id()
    print('{} branch of {}/{} at commit ID {}'.format(PROD_BRANCH, OWNER, REPO, prod_branch_commit_id))

    if dev_branch_commit_id != prod_branch_commit_id:
        # Check if dev branch is passing CI
        if dev_branch_state == 'success':
            print('Commit IDs differ and CI status is passing, starting clone and push')

            # Fetch github secrets
            with open('/secrets/github_app_key.pem', 'r') as pem:
                github_app_key = pem.read()
                print('Github secret has been read')

            generated_jwt = generate_jwt(github_app_key)
            print('JWT has been generated')

            token = fetch_github_token(generated_jwt)
            print('Github token received')

            # Clone repo
            repo_location = 'https://x-access-token:{}@github.com/{}/{}.git'.format(token, OWNER, REPO)
            output = git_clone_checkout_and_push(repo_location, PROD_BRANCH, DEV_BRANCH, REPO)
            print(output)
            print('Cloned {}/{} and pushed {} to {}'.format(OWNER, REPO, DEV_BRANCH, PROD_BRANCH))
        else:
            print('CI status is currently {}'.format(dev_branch_state))
    else:
        print('{} and {} branches share the same commit ID'.format(DEV_BRANCH, PROD_BRANCH))
