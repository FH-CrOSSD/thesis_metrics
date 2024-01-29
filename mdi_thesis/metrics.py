"""
Metrics

Author: Jacqueline Schmatz
Description: Formulas for metric calculation.
"""
from typing import Dict, Tuple, Union
import json
import collections
import math
import logging
from datetime import date, datetime, timedelta
from dateutil import relativedelta
# import numpy as np
import regex as re
import mdi_thesis.base.utils as utils
import mdi_thesis.external as external
from pathlib import Path
import os.path
import statistics


def maturity_level(
    base_data: Dict, filter_date: date, log: logging.Logger
) -> Dict[int, int]:
    """
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: Repositories with corresponding results.
    """
    repository_data = base_data.get("repository")
    issue_data = base_data.get("issue")
    release_data = base_data.get("release")
    repo_metric_dict = {}
    age_score = {}
    issue_score = {}
    release_score = {}
    if repository_data and issue_data and release_data:
        log.info("Data available. Starting calculation...")
        for repo, data in repository_data.items():
            created_at = data.get("created_at")
            created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").date()
            dates = relativedelta.relativedelta(filter_date, created_at)
            years = dates.years
            months = dates.months
            score = 0
            # Age > 3 years
            if (years == 3 and months > 0) or (years > 3):
                score = 5
            # Age > 2-3 years
            elif (years == 2 and months > 0) or (years == 3 and months == 0):
                score = 4
            # Age > 1-2 years
            elif (years == 2 and months == 0) or (years == 1 and months > 0):
                score = 3
            # Age 2-12 months
            elif (years == 1 and months == 0) or (years == 0 and months >= 2):
                score = 2
            # Age < 2 months
            elif years == 0 and months < 2:
                score = 1
            score = score / 5
            age_score[repo] = score

        score = 0
        for repo, data in issue_data.items():
            nr_of_issues = len(data)
            if nr_of_issues > 1000:
                score = 1
            elif nr_of_issues > 500 and nr_of_issues < 1000:
                score = 2
            elif nr_of_issues > 100 and nr_of_issues <= 500:
                score = 3
            elif nr_of_issues > 50 and nr_of_issues <= 100:
                score = 4
            elif nr_of_issues <= 50:
                score = 5
            score = score / 5
            issue_score[repo] = score

        for repo, releases in release_data.items():
            if releases:
                if len(releases) >= 1 and len(releases) <= 3:
                    score = 3
                else:
                    score = 5
            else:
                score = 1
            score = score / 5
            release_score[repo] = score
        if age_score:
            for repo, score in age_score.items():
                score_sum = score + issue_score[repo] + release_score[repo]
                result = score_sum / 3 * 100
                repo_metric_dict[repo] = result
    return repo_metric_dict


def osi_approved_license(base_data: Dict, log: logging.Logger) -> Dict[int, bool]:
    """
    Checks if a repos license is osi approved.
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: Repositories with corresponding results.
    """
    repository_data = base_data.get("repository")
    osi_licenses = external.get_osi_json()
    results = {}
    if repository_data:
        log.info("Data available. Starting calculation...")
        for repo, data in repository_data.items():
            license_return = None
            license_info = data.get("license")
            if not license_info:
                license_return = "not_provided"
            else:
                spdx_id = license_info.get("spdx_id").strip()
                for osi_license in osi_licenses:
                    licence_id = osi_license.get("licenseId").strip()
                    if spdx_id == licence_id:
                        osi_approved = osi_license.get("isOsiApproved")
                        if osi_approved is True:
                            license_return = "osi_approved"
                        elif osi_approved is False:
                            license_return = "not_osi_approved"
                        break
            if not license_return:
                license_return = "not_found"
            results[repo] = license_return
    else:
        log.info("No data available. Returning %s", results)
    return results


def technical_fork(
    base_data: Dict, log: logging.Logger
) -> Dict[int, Dict[str, Union[int, float]]]:
    """
    Total number of forks and average creation time.
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: Repositories with fork metrics and information.
    """
    fork_data = base_data.get("forks")
    repository_data = base_data.get("repository")
    fork_results = {}
    if repository_data and fork_data:
        log.info("Data available. Starting calculation...")
        for repo in repository_data:
            data = fork_data.get(repo)
            fork_nr = 0
            average_per_week = None
            if data:
                created_at_times = []
                for fork in data:
                    fork_created_at = fork.get("created_at")
                    fork_date = datetime.strptime(fork_created_at, "%Y-%m-%dT%H:%M:%SZ")
                    created_at_times.append(fork_date)
                    fork_id = fork.get("id")
                    if fork_id:
                        fork_nr += 1

                if created_at_times:
                    # Sort the datetime list
                    created_at_times.sort()
                    earliest_date = created_at_times[0].date()
                    latest_date = created_at_times[-1].date()
                    num_weeks = (latest_date - earliest_date).days // 7 + 1
                    # Count the number of elements per week
                    elements_per_week = [0] * num_weeks
                    for fork_datetime in created_at_times:
                        week_index = (fork_datetime.date() - earliest_date).days // 7
                        elements_per_week[week_index] += 1
                    average_per_week = round(statistics.fmean(elements_per_week))
            fork_results[repo] = {
                "total_forks": fork_nr,
                "average_forks_created_per_week": average_per_week,
            }
    else:
        log.info("No data available. Returning %s", fork_results)
    return fork_results


def criticality_score(
    base_data: Dict, filter_date: date, log: logging.Logger
) -> Dict[int, float]:
    """
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: criticality_score per repository.
    """
    scores_per_repo = {}
    criticality_score_per_repo = {}
    # created_since, updated_since
    repository_data = base_data.get("repository")
    contributor_data = base_data.get("contributors")
    commit_data = base_data.get("commits")
    release_data = base_data.get("release")
    issues_data = base_data.get("issue")
    issue_comments = base_data.get("issue_comments")
    dependents = base_data.get("downstream_dependencies")
    repo_organizations = base_data.get("organizations")
    if (
        repository_data
        and contributor_data
        and commit_data
        and release_data
        and issues_data
        and issue_comments
        and dependents
        and repo_organizations
    ):
        log.info("Data available. Starting calculation...")
        for repo, data in repository_data.items():
            created_at = data.get("created_at")
            created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
            updated_at = data.get("updated_at")
            updated_at = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ")
            dates = relativedelta.relativedelta(filter_date, created_at)
            months = dates.months + (dates.years * 12)
            diff_updated_today = relativedelta.relativedelta(filter_date, updated_at)
            diff_updated_today = diff_updated_today.months + (
                diff_updated_today.years * 12
            )
            scores_per_repo[repo] = {
                "created_since": months,
                "updated_since": diff_updated_today,
            }
            # contributor_count
            contributor_count = utils.get_contributors(
                contributors_data=contributor_data, check_contrib=True
            )
            cont_count = contributor_count.get(repo)
            if cont_count:
                scores_per_repo[repo].update({"contributor_count": cont_count})
            # org_count
            org_count = repo_organizations.get(repo)
            if org_count:
                org_num = len(org_count)
            else:
                org_num = 0
            scores_per_repo[repo].update({"org_count": org_num})
            # commit_frequency
            commits = commit_data.get(repo)
            average_per_week = 0
            repo_commit_dates = []
            if commits:
                for commit in commits:
                    try:
                        commit_date = commit.get("commit").get("author").get("date")
                        commit_date = datetime.strptime(
                            commit_date, "%Y-%m-%dT%H:%M:%SZ"
                        )
                        repo_commit_dates.append(commit_date)
                    except KeyError:
                        continue
                if len(repo_commit_dates) > 1:
                    # Sort the datetime list
                    repo_commit_dates.sort()
                    earliest_date = repo_commit_dates[0].date()
                    latest_date = repo_commit_dates[-1].date()
                    num_weeks = (latest_date - earliest_date).days // 7 + 1
                    # Count the number of elements per week
                    elements_per_week = [0] * num_weeks
                    for commit_datetime in repo_commit_dates:
                        week_index = (commit_datetime.date() - earliest_date).days // 7
                        elements_per_week[week_index] += 1
                    average_per_week = statistics.fmean(elements_per_week)
            scores_per_repo[repo].update({"commit_frequency": average_per_week})
            # recent_releases_count
            releases = release_data.get(repo)
            if releases:
                num_releases = len(releases)
            else:
                num_releases = 0
            scores_per_repo[repo].update({"recent_releases_count": num_releases})
            # closed_issues_count & updated_issues_count
            issues_list = issues_data.get(repo)
            closed_issues = 0
            updated_issues = 0
            if issues_list:
                for issue in issues_list:
                    closed_at = issue.get("closed_at")
                    updated_at = issue.get("updated_at")
                    if closed_at:
                        closed_date = datetime.strptime(
                            closed_at, "%Y-%m-%dT%H:%M:%SZ"
                        ).date()
                        closed_diff = filter_date - closed_date
                        if closed_diff.days <= 90:
                            closed_issues += 1
                    if updated_at:
                        updated_date = datetime.strptime(
                            updated_at, "%Y-%m-%dT%H:%M:%SZ"
                        ).date()
                        updated_diff = filter_date - updated_date
                        if updated_diff.days <= 90:
                            updated_issues += 1
            scores_per_repo[repo].update(
                {
                    "closed_issues_count": closed_issues,
                    "updated_issues_count": updated_issues,
                }
            )
            # comment_frequency
            issues_dict = issue_comments.get(repo)
            avg_comment_count = 0
            if issues_dict:
                comment_count_list = []
                for issue, comments in issues_dict.items():
                    comment_len = 0
                    for comment in comments:
                        if comment.get("id"):
                            comment_updated_at = comment.get("updated_at")
                            comment_updated_at = datetime.strptime(
                                comment_updated_at, "%Y-%m-%dT%H:%M:%SZ"
                            ).date()
                            if comment_updated_at > filter_date:
                                comment_len += 1
                    comment_count_list.append(comment_len)
                if comment_count_list:
                    avg_comment_count = statistics.fmean(comment_count_list)
            scores_per_repo[repo].update({"comment_frequency": avg_comment_count})
            # dependents_count
            downstream_dep = dependents.get(repo)
            dep_count = 0
            if downstream_dep:
                dep_count = downstream_dep.get("total_dependents")
            scores_per_repo[repo].update({"dependents_count": dep_count})

    source_path = Path(__file__).resolve()
    source_dir = source_path.parent

    weights_json = open(os.path.join(source_dir,"criticality_score_weights.json"), encoding="utf-8")
    # weights_json = open(
    #     r"mdi_thesis\criticality_score_weights.json",
    #     encoding="utf-8")
    weights = json.load(weights_json)
    weight_sum = 0
    for elements in weights.values():
        weight = elements.get("weight")
        weight_sum += weight
    for repo, param in scores_per_repo.items():
        form_1 = 1 / weight_sum
        sum_alpha = 0
        for param_name, value in param.items():
            log_1 = math.log(1 + value)
            max_threshold = weights.get(param_name).get("max_threshold")
            log_2 = math.log(1 + max(value, max_threshold))
            if log_2 == 0:
                res_fraction = 1
            else:
                res_fraction = log_1 / log_2
            weight = weights.get(param_name).get("weight")
            res_1 = weight * res_fraction
            sum_alpha += res_1
        res_2 = round((form_1 * sum_alpha), 2) * 100
        criticality_score_per_repo[repo] = res_2

    return criticality_score_per_repo


def pull_requests(base_data: Dict, log: logging.Logger) -> Dict[int, Dict[str, float]]:
    """
    Contains information about:
    - Total number of pulls
    - Average closing time (Difference of creation and close date)
    - Ratio per state (open, closed and merged)
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: Parameter names and values
    """
    pulls_data = base_data.get("pull_requests")
    repository_data = base_data.get("repository")
    pull_results = {}
    if repository_data and pulls_data:
        log.info("Data available. Starting calculation...")
        for repo in repository_data:
            data = pulls_data.get(repo)
            state_open = 0
            state_closed = 0
            pulls_merged = 0
            avg_date_diff = None
            ratio_open = None
            ratio_closed = None
            ratio_merged = None
            total_pulls = len(data)
            date_diffs = []
            if data:
                for pull in data:
                    state = pull.get("state")
                    closed_at = pull.get("closed_at")
                    created_at = pull.get("created_at")
                    merged_at = pull.get("merged_at")
                    created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                    if closed_at:
                        closed_at = datetime.strptime(closed_at, "%Y-%m-%dT%H:%M:%SZ")
                    if merged_at:
                        merged_at = datetime.strptime(merged_at, "%Y-%m-%dT%H:%M:%SZ")
                        pulls_merged += 1
                        if closed_at:
                            if closed_at == merged_at:
                                date_diff = closed_at - created_at
                                date_diffs.append(date_diff.days)
                    if state == "open":
                        state_open += 1
                    elif state == "closed":
                        state_closed += 1
                if len(date_diffs) > 0:
                    avg_date_diff = statistics.fmean(date_diffs)

                if total_pulls > 0:
                    ratio_open = (state_open / total_pulls) * 100
                    ratio_closed = (state_closed / total_pulls) * 100
                    ratio_merged = (pulls_merged / total_pulls) * 100
            pull_results[repo] = {
                "total_pulls": total_pulls,
                "avg_pull_closing_days": avg_date_diff,
                "ratio_open_total": ratio_open,
                "ratio_closed_total": ratio_closed,
                "ratio_merged_total": ratio_merged,
            }
    else:
        log.info("No data available. Returning %s", pull_results)
    return pull_results


def project_velocity(
    base_data: Dict, log: logging.Logger
) -> Dict[int, Dict[str, float]]:
    """
    Calculates information about a projects velocity concerning
    issues and their resolving time. Issues also include pulls,
    bc. all pulls are issues, but not all issues are pulls
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: Values for each information including the
    total number of issues, the average issue resolving time in days,
    the ratio of open and closed issues to total issues and
    information about the number of pulls.
    """
    velocity_results = {}
    issues_pulls = base_data.get("issue")
    repository_data = base_data.get("repository")
    if repository_data and issues_pulls:
        log.info("Data available. Starting calculation...")
        for repo in repository_data:
            data = issues_pulls.get(repo)
            closed_issues = 0
            open_issues = 0
            total_issues = len(data)
            date_diffs = []
            pull_issue_list = []
            ratio_open = None
            ratio_closed = None
            ratio_pull_issue = None
            avg_date_diff = None
            pull_count = None
            no_pull_count = None
            if data:
                for issue in data:
                    pull_request_id = issue.get("pull_request")
                    is_pull_request = bool(pull_request_id)
                    pull_issue_list.append(is_pull_request)
                    state = issue.get("state")
                    created_at = issue.get("created_at")
                    created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                    if state == "open":
                        open_issues += 1
                    elif state == "closed":
                        closed_issues += 1
                        closed_at = issue.get("closed_at")
                        if closed_at:
                            closed_at = datetime.strptime(
                                closed_at, "%Y-%m-%dT%H:%M:%SZ"
                            )
                        date_diff = closed_at - created_at
                        date_diffs.append(date_diff.days)
                pull_count = pull_issue_list.count(True)
                no_pull_count = pull_issue_list.count(False)
                if len(date_diffs) > 0:
                    avg_date_diff = round(statistics.fmean(date_diffs))
                if total_issues > 0:
                    ratio_open = (open_issues / total_issues) * 100
                    ratio_closed = (closed_issues / total_issues) * 100
                    ratio_pull_issue = (pull_count / total_issues) * 100
            velocity_results[repo] = {
                "total_issues": total_issues,
                "closed_issues": closed_issues,
                "open_issues": open_issues,
                "pull_count": pull_count,
                "no_pull_count": no_pull_count,
                "ratio_pull_issue": ratio_pull_issue,
                "avg_issue_resolving_days": avg_date_diff,
                "ratio_open_total": ratio_open,
                "ratio_closed_total": ratio_closed,
            }
    else:
        log.info("No data available. Returning %s", velocity_results)
    return velocity_results


def github_community_health_percentage(
    base_data: Dict, log: logging.Logger
) -> Dict[int, Dict[str, Union[float, bool]]]:
    """
    Retrieves information about the GitHub community health percentage metric.
    As the formula introduced by GitHub is questionable, potential relevant
    information is summarized by indicating,
    if it is available (True) or not (False).
    This is implied by the outdated formula,
    referring to the existence of certain files
    (readme, contributing, license, code of conduct).
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: Scores and potentially relevant information
    """
    community_health_info = {}
    community_health = base_data.get("community_health")
    if community_health:
        log.info("Data available. Starting calculation...")
        for repo, data in community_health.items():
            score = data.get("health_percentage")
            description = bool(data.get("description"))
            documentation = bool(data.get("documentation"))
            code_of_conduct = bool(data.get("files").get("code_of_conduct"))
            contributing = bool(data.get("files").get("contributing"))
            issue_template = bool(data.get("files").get("issue_template"))
            pull_request_template = bool(data.get("files").get("pull_request_template"))
            license_bool = bool(data.get("files").get("license"))
            readme = bool(data.get("files").get("readme"))
            info_list = [
                description,
                documentation,
                code_of_conduct,
                contributing,
                issue_template,
                pull_request_template,
                license_bool,
                readme,
            ]
            true_count = info_list.count(True)
            false_count = info_list.count(False)
            if sum(info_list) > 0:
                custom_health_percentage = (sum(info_list) / len(info_list)) * 100
            else:
                custom_health_percentage = None
            infos = {
                "community_health_score": score,
                "custom_health_score": custom_health_percentage,
                "true_count": true_count,
                "false_count": false_count,
                "description": description,
                "documentation": documentation,
                "code_of_conduct": code_of_conduct,
                "contributing": contributing,
                "issue_template": issue_template,
                "pull_request_template": pull_request_template,
                "license": license_bool,
                "readme": readme,
            }
            community_health_info[repo] = infos
    else:
        log.info("No data available. Returning %s", community_health_info)
    return community_health_info


def issues(
    base_data: Dict, filter_date: date, log: logging.Logger
) -> Dict[int, Dict[str, float]]:
    """
    Returns information about issues, excluding pulls.
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: Selected information about a repositories issue activities
    """
    issues_infos = {}
    issues_data = base_data.get("issue")
    issue_comments = base_data.get("issue_comments")
    repository_data = base_data.get("repository")
    if repository_data and issues_data and issue_comments:
        log.info("Data available. Starting calculation...")
        for repo in repository_data:
            data = issues_data.get(repo)
            closed_issues = 0
            open_issues = 0
            total_issues = 0
            issue_close_times = []
            issue_first_response_times = []
            issue_creation_times = []
            issues_created_since = []
            comment_count_list = []
            ratio_open = None
            ratio_closed = None
            new_ratio = None
            avg_issue_comments = None
            avg_first_response_time_days = None
            avg_date_diff = None
            average_per_week = None
            if data:
                for issue in data:
                    pull_request_id = issue.get("pull_request")
                    is_pull_request = bool(pull_request_id)
                    if not is_pull_request:
                        total_issues += 1
                        state = issue.get("state")
                        issue_created_at = issue.get("created_at")
                        issue_created_at = datetime.strptime(
                            issue_created_at, "%Y-%m-%dT%H:%M:%SZ"
                        )
                        if isinstance(issue_created_at, datetime):
                            issue_created_at = issue_created_at.date()
                        if issue_created_at >= filter_date:
                            issues_created_since.append(issue_created_at)
                        issue_creation_times.append(issue_created_at)
                        issue_number = issue.get("number")
                        # Issue comments are only counted if comments have an id
                        # Comments without an id are not created by an user
                        total_comments = 0
                        issue_comments_repo = issue_comments.get(repo)
                        first_response_time = None
                        if issue_comments_repo:
                            comments = issue_comments_repo.get(str(issue_number))
                            if comments:
                                for comment in comments:
                                    comment_id = comment.get("id")
                                    if comment_id:
                                        total_comments += 1
                                comment_count_list.append(total_comments)
                                # first_comment_date = issue_comments.get(
                                #     repo).get(issue_number)[0].get("created_at")
                                first_comment_date = comments[0].get("created_at")
                                if first_comment_date:
                                    first_comment_date = datetime.strptime(
                                        first_comment_date, "%Y-%m-%dT%H:%M:%SZ"
                                    )
                                    if isinstance(first_comment_date, datetime):
                                        first_comment_date = first_comment_date.date()
                                    first_response_time = (
                                        first_comment_date - issue_created_at
                                    )
                                    first_response_time = first_response_time.days
                                    issue_first_response_times.append(
                                        first_response_time
                                    )
                        # Count states
                        if state == "open":
                            open_issues += 1
                        if state == "closed":
                            closed_issues += 1
                            closed_at = issue.get("closed_at")
                            if closed_at:
                                closed_at = datetime.strptime(
                                    closed_at, "%Y-%m-%dT%H:%M:%SZ"
                                )
                                if isinstance(closed_at, datetime):
                                    closed_at = closed_at.date()
                            date_diff = closed_at - issue_created_at
                            issue_close_times.append(date_diff.days)
                if len(issue_creation_times) > 1:
                    # Sort the datetime list
                    issue_creation_times.sort()
                    earliest_date = issue_creation_times[0]
                    if isinstance(earliest_date, datetime):
                        earliest_date = earliest_date.date()
                    latest_date = issue_creation_times[-1]
                    if isinstance(latest_date, datetime):
                        latest_date = latest_date.date()
                    num_weeks = (latest_date - earliest_date).days // 7 + 1
                    # Count the number of elements per week
                    elements_per_week = [0] * num_weeks
                    for issue_datetime in issue_creation_times:
                        if isinstance(issue_datetime, datetime):
                            issue_datetime = issue_datetime.date()
                        week_index = (issue_datetime - earliest_date).days // 7
                        elements_per_week[week_index] += 1
                    average_per_week = round(statistics.fmean(elements_per_week))
                if issue_close_times:
                    avg_date_diff = round(statistics.fmean(issue_close_times))
                if issue_first_response_times:
                    avg_first_response_time_days = round(
                        statistics.fmean(issue_first_response_times)
                    )
                if comment_count_list:
                    avg_issue_comments = round(statistics.fmean(comment_count_list))
                if total_issues:
                    ratio_open = (open_issues / total_issues) * 100
                    ratio_closed = (closed_issues / total_issues) * 100
                    new_ratio = (len(issues_created_since) / total_issues) * 100

            issues_infos[repo] = {
                "total_issues": total_issues,
                "open_issues": open_issues,
                "closed_issues": closed_issues,
                "new_issues": len(issues_created_since),
                "new_ratio": new_ratio,
                "average_issues_created_per_week": average_per_week,
                "average_issue_comments": avg_issue_comments,
                "average_issue_resolving_days": avg_date_diff,
                "average_first_response_time_days": avg_first_response_time_days,
                "ratio_open_total": ratio_open,
                "ratio_closed_total": ratio_closed,
            }
    else:
        log.info("No data available. Returning %s", issues_infos)

    return issues_infos


def support_rate(base_data: Dict, log: logging.Logger) -> Dict[int, float]:
    """
    The support rate uses issues and pulls which received a response
    in the last 6 months. Pulls are excluded from the issues
    (bc. pulls are also included in queried issues data).
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: Support rate for each repository.
    """
    support_rate_results = {}
    # All issues required to get information about pulls in issue data
    issues_pulls = base_data.get("issue")
    issue_comments = base_data.get("issue_comments")
    repository_data = base_data.get("repository")
    if repository_data and issues_pulls and issue_comments:
        log.info("Data available. Starting calculation...")
        for repo in repository_data:
            data = issues_pulls.get(repo)
            issue_flag = {}
            support_rate_val = None
            total_issues = 0
            total_pulls = 0
            issues_with_response = 0
            pulls_with_response = 0
            if data:
                for issue in data:
                    pull_request_id = issue.get("pull_request")
                    is_pull_request = bool(pull_request_id)
                    issue_number = issue.get("number")
                    issue_flag[str(issue_number)] = is_pull_request
                    if is_pull_request:
                        total_pulls += 1
                    else:
                        total_issues += 1
                issue_comment_data = issue_comments.get(repo)
                if issue_comment_data:
                    for issue, comments in issue_comment_data.items():
                        # If issue is no pull
                        if not issue_flag.get(issue):
                            # total_issues += 1
                            if comments:
                                for comment in comments:
                                    comment_id = comment.get("id")
                                    if comment_id:
                                        issues_with_response += 1
                                        break
                        else:
                            # total_pulls += 1
                            if comments:
                                for comment in comments:
                                    comment_id = comment.get("id")
                                    if comment_id:
                                        pulls_with_response += 1
                                        break
                if total_issues > 0:
                    issue_support = issues_with_response / total_issues
                else:
                    issue_support = 0
                if total_pulls > 0:
                    pulls_support = pulls_with_response / total_pulls
                else:
                    pulls_support = 0
                support_rate_val = ((issue_support + pulls_support) / 2) * 100
            support_rate_results[repo] = support_rate_val
    else:
        log.info("No data available. Returning %s", support_rate_results)
    return support_rate_results


def code_dependency(base_data: Dict, log: logging.Logger) -> Dict[int, Dict]:
    """
    Dependencies retrieved from GitHub's Dependency Graph.
    Upstream dependencies show on how many other projects
    the passed repositories depend on -> GitHub Dependencies.
    Downstream shoe how many other repositories depend on the
    passed repositories -> GitHub Dependents.
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: total upstream and downstream dependencies +
    Visible downstream dependencies
    """
    dependencies = {}
    upstream_dependencies = base_data.get("upstream_dependencies")
    downstream_dependencies = base_data.get("downstream_dependencies")
    repository_data = base_data.get("repository")
    if repository_data and downstream_dependencies and upstream_dependencies:
        log.info("Data available. Starting calculation...")
        for repo in repository_data:
            data = downstream_dependencies.get(repo)
            total_upstream = 0
            total_downstream = 0
            if data:
                for upstream_dep in upstream_dependencies.get(repo):
                    # Python dependencies may contain only value "-"
                    if upstream_dep != "-":
                        total_upstream += 1
                total_downstream = data.get("total_dependents")
            dependencies[repo] = {
                "total_upstream": total_upstream,
                "total_downstream": total_downstream,
            }
    else:
        log.info("No data available. Returning %s", dependencies)
    return dependencies


def security_advisories(
    base_data: Dict, log: logging.Logger
) -> Tuple[
    Dict[int, Dict[str, Union[int, float, None]]],
    Dict[int, Dict[str, Union[int, float, str, bool]]],
]:
    """
    Uses GitHub's security advisories to retrieve information and calculate
    basic scores.
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: Two dictionaries, containing scores and raw information
    """
    repo_advisories = base_data.get("advisories")
    repository_data = base_data.get("repository")
    advisory_infos = {}
    advisory_scores = {}
    if repository_data and repo_advisories:
        log.info("Data available. Starting calculation...")
        for repo in repository_data:
            advisory = repo_advisories.get(repo)
            advisories_available = bool(advisory)
            advisories = {}
            vuln_patched = 0
            vuln_not_patched = 0
            cvss_scores = []
            closed_adv = 0
            severities = []
            scores = {}
            if advisory:
                for adv in advisory:
                    # On GitHub, advisories can only be set to withdrawn
                    # by contacting the support if the advisory was made in error.
                    withdrawn_at = bool(adv.get("withdrawn_at"))
                    if withdrawn_at:
                        continue
                    adv_id = adv.get("ghsa_id")
                    cve_id = adv.get("cve_id")
                    severity = adv.get("severity")  # low, medium, high, critical
                    severities.append(severity)
                    state = adv.get("state")  # triage, draf, published or closed
                    if state == "closed":
                        closed_adv += 1
                    published_at = adv.get("published_at")
                    cvss_score = adv.get("cvss").get("score")
                    if not cvss_score:
                        if cve_id:
                            # if no score was provided but an id is available,
                            # NVD is checked.
                            cvss_score = external.get_nvds(cve_id)
                    if cvss_score:
                        cvss_scores.append(cvss_score)
                    cwes = adv.get("cwes")
                    vulnerabilities = adv.get("vulnerabilities")
                    if vulnerabilities:
                        for vul_dict in vulnerabilities:
                            # package_name = vul_dict.get("package").get("name")
                            package_patched = bool(vul_dict.get("patched_versions"))
                            if package_patched:
                                vuln_patched += 1
                            else:
                                vuln_not_patched += 1

                    advisories[adv_id] = {
                        "cve_id": cve_id,
                        "severity": severity,
                        "state": state,
                        "published_at": published_at,
                        "cvss_score": cvss_score,
                        "cwes": cwes,
                    }
                severity_high_count = severities.count("high")
                severity_critical_count = severities.count("critical")
                severity_high_critical_total = (
                    severity_high_count + severity_critical_count
                )
                if severities:
                    ratio_severity_high_crit = (
                        severity_high_critical_total / len(severities)
                    ) * 100
                else:
                    ratio_severity_high_crit = None
                if cvss_scores:
                    mean_cvs_score = statistics.fmean(cvss_scores)
                else:
                    mean_cvs_score = None
                total_vuln = vuln_patched + vuln_not_patched
                if total_vuln > 0:
                    patch_ratio = (vuln_patched / total_vuln) * 100
                else:
                    patch_ratio = None
                scores = {
                    "advisories_available": advisories_available,
                    "patch_ratio": patch_ratio,
                    "closed_advisories": closed_adv,
                    "average_cvss_score": mean_cvs_score,
                    "ratio_severity_high_crit": ratio_severity_high_crit,
                }
            advisory_scores[repo] = scores
            advisory_infos[repo] = advisories
    else:
        log.info(
            "No data available. Returning %s - %s", advisory_scores, advisory_infos
        )
    return advisory_scores, advisory_infos


def contributions_distributions(
    base_data: Dict, log: logging.Logger
) -> Dict[int, Dict[str, Union[int, float]]]:
    """
    Includes Bus Factor and Scores representing the Pareto Principle.
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: Information about the distribution of the contributions per
    contributors by calculating the bus factor and the pareto principle
    for each repository.
    """
    repo_pareto = {}
    commits_data = base_data.get("commits")
    single_commits = base_data.get("single_commits")
    repository_data = base_data.get("repository")
    # RoF metrics
    if repository_data and single_commits and commits_data:
        log.info("Data available. Starting calculation...")
        for repo in repository_data:
            commit_list = single_commits.get(repo)
            rof_pareto_tail = None
            rof_pareto_dominant = None
            rof_prot_diff = None
            avg_num_contributors_per_file = None
            rof_per_contributor = []
            if commit_list:
                file_committer = utils.get_contributor_per_files(commit_list)
                total_files = len(file_committer)
                num_contributors_per_files = []
                if file_committer:
                    for committer_ids in file_committer.values():
                        num_contributors_per_files.append(len(committer_ids))
                    avg_num_contributors_per_file = statistics.fmean(num_contributors_per_files)
                else:
                    avg_num_contributors_per_file = None
                committer_per_file = utils.invert_dict(file_committer)
                for contributor, files in committer_per_file.items():
                    ratio_of_files = (len(files)) / total_files
                    rof_per_contributor.append(ratio_of_files)

                rof_per_contributor.sort(reverse=True)
                total_file_contributions = sum(rof_per_contributor)
                total_file_contributer = len(rof_per_contributor)
                eighty_percent = total_file_contributions * 0.8
                running_contributions = 0
                rof_pareto_ist = 0
                rof_prot_diff = 0
                rof_pareto_ist_percentage = 0
                # Calculate the percentage of contributors which contribute
                # 80 % of the contributions
                for contrib, contributions in enumerate(rof_per_contributor, start=1):
                    running_contributions += contributions
                    # if contrib == math.ceil(twenty_percent):
                    if running_contributions >= eighty_percent:
                        rof_pareto_ist = contrib
                        rof_pareto_ist_percentage = (
                            rof_pareto_ist / total_file_contributer
                        )
                        break
                rof_pareto_dominant = rof_pareto_ist_percentage * 100
                rof_pareto_tail = 100 - rof_pareto_dominant
                rof_prot_diff = abs(20 - rof_pareto_dominant)
            pareto_results = {
                "RoF_tail": rof_pareto_tail,
                "RoF_dominant": rof_pareto_dominant,
                "RoF_diff_percent": rof_prot_diff,
                "avg_num_contributors_per_file": avg_num_contributors_per_file,
            }

            repo_pareto[repo] = pareto_results

        # NoC metrics
        for repo in repository_data:
            commits = commits_data.get(repo)
            total_committer = []
            no_committer = 0
            bus_factor_score = None
            noc_pareto_tail = None
            noc_pareto_dominant = None
            noc_prot_diff = None
            if commits:
                for commit in commits:
                    contributor = None
                    co_author = None
                    commit_elem = commit.get("commit")
                    if commit_elem:
                        verification = commit_elem.get("verification")
                        if verification:
                            verified = verification.get("verified")
                            if verified:
                                committer = commit_elem.get("author")
                            else:
                                committer = commit_elem.get("committer")
                        else:
                            committer = commit_elem.get("committer")
                        if not committer:
                            no_committer += 1
                        else:
                            contributor = committer.get("email")
                        message = commit_elem.get("message")
                        co_author_line = re.findall(r"Co-authored-by:(.*?)>", message)
                        for value in co_author_line:
                            co_author = value.split("<")[-1]
                            total_committer.append(co_author)
                    else:
                        log.debug("No commit: %s", commit)
                    total_committer.append(contributor)
                committer_counter = collections.Counter(total_committer).values()
                commits_sorted = sorted(committer_counter, reverse=True)
                t_1 = sum(committer_counter) * 0.5
                t_2 = 0
                bus_factor_score = 0
                total_contributions = sum(commits_sorted)
                total_contributer = len(commits_sorted)
                eighty_percent = total_contributions * 0.8
                running_contributions = 0
                noc_pareto_ist = 0
                noc_prot_diff = 0
                noc_pareto_ist_percentage = 0
                # Calculate the percentage of contributors which contribute
                # 80 % of the contributions
                for contrib, contributions in enumerate(commits_sorted, start=1):
                    running_contributions += contributions
                    if running_contributions >= eighty_percent:
                        noc_pareto_ist = contrib
                        noc_pareto_ist_percentage = noc_pareto_ist / total_contributer
                        break
                    if t_2 <= t_1:
                        t_2 += contributions
                        bus_factor_score += 1
                noc_pareto_dominant = noc_pareto_ist_percentage * 100
                noc_pareto_tail = 100 - noc_pareto_dominant
                noc_prot_diff = abs(20 - noc_pareto_dominant)
            pareto_results = {
                "bus_factor_score": bus_factor_score,
                "NoC_tail": noc_pareto_tail,
                "NoC_dominant": noc_pareto_dominant,
                "NoC_diff_percent": noc_prot_diff,
            }
            if repo in repo_pareto:
                repo_pareto[repo].update(pareto_results)

    else:
        log.info("No data available. Returning %s", repo_pareto)
    return repo_pareto


def number_of_support_contributors(
    base_data: Dict, log: logging.Logger
) -> Dict[int, int]:
    """
    Calculates the number of active contributors per repository
    in the last 6 months and assigns a score to each.
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: Score for the number of active contributors
    """
    commits_data = base_data.get("commits")
    repository_data = base_data.get("repository")
    support_contributors = {}
    if repository_data and commits_data:
        log.info("Data available. Starting calculation...")
        for repo in repository_data:
            commits = commits_data.get(repo)
            total_committer = set()
            score = 0
            if commits:
                for commit in commits:
                    try:
                        committer_id = commit.get("committer").get("id")
                        total_committer.add(committer_id)
                    except AttributeError:
                        pass
                total_committer = len(total_committer)
                if total_committer < 5:
                    score = 1
                elif total_committer >= 5 and total_committer <= 10:
                    score = 2
                elif total_committer > 10 and total_committer <= 20:
                    score = 3
                elif total_committer > 20 and total_committer <= 50:
                    score = 4
                elif total_committer > 50:
                    score = 5
            result_score = score / 5 * 100
            support_contributors[repo] = result_score
    else:
        log.info("No data available. Returning %s", support_contributors)
    return support_contributors


def elephant_factor(base_data: Dict, log: logging.Logger) -> Dict[int, int]:
    """
    Calculates the elephant factor (distribution of contributions
    by organizations user belong to) for each repository.
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: Elephant factor for each repository
    """
    contributor_data = base_data.get("contributors")
    users_data = base_data.get("organization_users")
    repository_data = base_data.get("repository")
    repo_elephant_factor = {}
    if repository_data and contributor_data and users_data:
        log.info("Data available. Starting calculation...")
        for repo in repository_data:
            contributors = contributor_data.get(repo)
            elephant_factor_score = 0
            if contributors:
                org_contributions = {}
                user_contributions = {}
                for user in contributors:
                    if isinstance(user, dict):
                        login = user.get("login")
                        contributions = user.get("contributions")
                        user_contributions[login] = contributions
                users = users_data.get(repo)
                if users:
                    for user, organizations in users.items():
                        for organization in organizations:
                            if isinstance(organization, dict):
                                if "login" in organization.keys():
                                    org_name = organization.get("login")
                                    user_contrib = user_contributions.get(user)
                                    if org_name and user_contrib:
                                        if org_name in org_contributions:
                                            org_contributions[org_name] += user_contrib
                                        else:
                                            org_contributions[org_name] = user_contrib
                            else:
                                if "login" in organizations.keys():
                                    org_name = organizations.get("login")
                                    user_contrib = user_contributions.get(user)
                                    if org_name and user_contrib:
                                        if org_name in org_contributions:
                                            org_contributions[org_name] += user_contrib
                                        else:
                                            org_contributions[org_name] = user_contrib
                    t_1 = sum(org_contributions.values()) * 0.5
                    t_2 = 0
                    orgs_sorted = sorted(org_contributions.values(), reverse=True)
                    for org_count in orgs_sorted:
                        if isinstance(org_count, int) and t_2 <= t_1:
                            t_2 += org_count
                            elephant_factor_score += 1
            repo_elephant_factor[repo] = elephant_factor_score
    else:
        log.info("No data available. Returning %s", repo_elephant_factor)
    return repo_elephant_factor


def size_of_community(base_data: Dict, log: logging.Logger) -> Dict[int, float]:
    """
    The size of community includes contributors and subscribers.
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: Size of community score for each repository
    """
    repo_community = {}
    repository_data = base_data.get("repository")
    contributors_data = base_data.get("contributors")
    contributor_count = utils.get_contributors(contributors_data, check_contrib=False)
    if repository_data:
        log.info("Data available. Starting calculation...")
        for repo, data in repository_data.items():
            score = 0
            subscribers_count = data.get("subscribers_count")
            cont_count = contributor_count.get(repo)
            community_count = subscribers_count + cont_count
            if community_count < 50:
                score = 1
            elif community_count >= 50 and community_count <= 100:
                score = 2
            elif community_count > 100 and community_count <= 200:
                score = 3
            elif community_count > 200 and community_count <= 300:
                score = 4
            elif community_count > 300:
                score = 5
            community_score = (score / 5) * 100
            repo_community[repo] = community_score
    else:
        log.info("No data available. Returning %s", repo_community)
    return repo_community


def churn(base_data: Dict, log: logging.Logger) -> Dict[int, float]:
    """
    Score, representing the code change turn ratio.
    :param data_object: Request object, required to gather data
    of already selected repositories.
    :return: Churn score each repository
    """
    results_dict = {}
    single_commits = base_data.get("single_commits")
    repository_data = base_data.get("repository")
    if repository_data and single_commits:
        log.info("Data available. Starting calculation...")
        for repo in repository_data:
            commits = single_commits.get(repo)
            churn_score = None
            if commits:
                lines_added = 0
                lines_deleted = 0
                churn_score = 0
                for features in commits.values():
                    for row in features:
                        stats = row.get("stats")
                        additions = stats.get("additions")
                        deletions = stats.get("deletions")
                        lines_added += additions
                        lines_deleted += deletions
                if lines_added > 0:
                    churn_score = (lines_deleted / lines_added) * 100
                else:
                    churn_score = None
            results_dict[repo] = churn_score
    else:
        log.info("No data available. Returning %s", results_dict)
    return results_dict


def branch_lifecycle(
    base_data: Dict, filter_date: date, log: logging.Logger
) -> Dict[int, Dict]:
    """
    Note: avg datediff has less information value if last created branch
    was created years ago.
    """
    stale_branch_states = base_data.get("stale_branches")
    active_branch_states = base_data.get("active_branches")
    branches_data = base_data.get("branches")
    repository_data = base_data.get("repository")
    branch_results = {}
    if repository_data and branches_data:
        log.info("Data available. Starting calculation...")
        for repo in repository_data:
            branches = branches_data.get(repo)
            branch_creation_frequency_days = None
            branch_avg_age_days = None
            stale_ratio = None
            active_ratio = None
            unresolved_ratio = None
            resolved_ratio = None
            branch_state_counter = None
            if branches:
                dates = []
                open_dates = []
                all_branches = {}
                total_stale = 0
                total_active = 0
                if stale_branch_states:
                    total_stale = len(stale_branch_states.get(repo))
                    all_branches.update(stale_branch_states[repo])
                if active_branch_states:
                    total_active = len(active_branch_states.get(repo))
                    all_branches.update(active_branch_states[repo])
                total_branches = len(all_branches)
                branch_state_counter = collections.Counter(all_branches.values())
                for branch, elements in branches.items():
                    elem = elements[0]
                    if branch != "master":
                        commit = elem.get("commit")
                        if commit:
                            commit_date = (
                                elem.get("commit")
                                .get("commit")
                                .get("author")
                                .get("date")
                            )
                            commit_date = datetime.strptime(
                                commit_date, "%Y-%m-%dT%H:%M:%SZ"
                            )
                            if isinstance(commit_date, datetime):
                                commit_date = commit_date.date()
                        else:
                            continue
                        dates.append(commit_date)
                        branch_state = all_branches.get(branch)
                        if branch_state not in ["Closed", "Merged"]:
                            open_dates.append(commit_date)

                if total_branches > 0:
                    total_merged = branch_state_counter["Merged"]
                    total_compare = branch_state_counter["Compare"]
                    total_open = branch_state_counter["Open"]
                    total_closed = branch_state_counter["Closed"]
                    # Calculations
                    stale_ratio = (total_stale / total_branches) * 100
                    active_ratio = (total_active / total_branches) * 100
                    unresolved_total = total_open + total_compare
                    resolved_total = total_closed + total_merged
                    unresolved_ratio = (unresolved_total / total_branches) * 100
                    resolved_ratio = (resolved_total / total_branches) * 100
                else:
                    stale_ratio = None
                    active_ratio = None
                    unresolved_ratio = None
                    resolved_ratio = None

                # Calculating time metrics
                dates.sort()
                total_dates = len(dates)
                time_difference = timedelta(0)
                if isinstance(time_difference, datetime):
                    time_difference = time_difference.date()
                time_diff_till_today = timedelta(0)
                # Ensure datatype is date instead of datetime
                if isinstance(time_diff_till_today, datetime):
                    time_diff_till_today = time_diff_till_today.date()
                if isinstance(filter_date, datetime):
                    filter_date = filter_date.date()
                # Calculate age for each date
                for open_date in open_dates:
                    time_diff_till_today += filter_date - open_date
                counter = 0
                for i in range(1, len(dates), 1):
                    counter += 1
                    time_difference += dates[i] - dates[i - 1]
                # Time frequencies are only considered to be valid
                # when at least 2 values exist
                if total_dates > 1 and len(open_dates) > 0:
                    branch_avg_age = time_diff_till_today / len(open_dates)
                    branch_avg_age_days = branch_avg_age.days
                    branch_creation_frequency = time_difference / counter
                    branch_creation_frequency_days = branch_creation_frequency.days
                else:
                    branch_avg_age_days = None
                    branch_creation_frequency_days = None
            branch_results[repo] = {
                "branch_creation_frequency_days": branch_creation_frequency_days,
                "branch_avg_age_days": branch_avg_age_days,
                "stale_ratio": stale_ratio,
                "active_ratio": active_ratio,
                "unresolved_ratio": unresolved_ratio,
                "resolved_ratio": resolved_ratio,
                "branch_state_counter": branch_state_counter,
            }
    else:
        log.info("No data available. Returning %s", branch_results)
    return branch_results
