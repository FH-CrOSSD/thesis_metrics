"""
Base Requests

Author: Jacqueline Schmatz
Description: Requests for data collection.
"""

import os
import json
import time
from typing import Dict, List, Any, Union
import logging
import math
import re
from urllib.error import HTTPError
from pathlib import Path
from datetime import datetime
from dateutil import relativedelta
from bs4 import BeautifulSoup
import requests
import mdi_thesis.constants as constants
import mdi_thesis.base.utils as utils


def get_logger(name: str) -> logging.Logger:
    """
    Getting logger with log settings.
    :param name: Logger name.
    :return: logger object with adjusted settings.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        console = logging.StreamHandler()
        logger.addHandler(console)
        log_formatting = ("%(asctime)s - %(levelname)s " +
                          "- line: " +
                          "%(lineno)s - %(funcName)s - " +
                          "%(module)s - %(message)s")
        formatter = logging.Formatter(log_formatting)
        console.setFormatter(formatter)
        logger.setLevel(logging.DEBUG)
        curr_path = Path(os.path.dirname(__file__))
        log_path = curr_path.parents[1]
        file_name = datetime.now().strftime('logger_%Y%m%d_%H_%M')
        file_path = os.path.join("outputs/logs/", file_name)
        file_handler = logging.FileHandler(f"{log_path}/{file_path}.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


class Request:
    """
    Class for GitHub Request
    """
    def __init__(self, filter_date) -> None:
        self.token = constants.API_TOKEN
        self.results_per_page = 100
        self.headers = {"Authorization": "token " + self.token}
        self.session = requests.Session()
        self.response = requests.Response()
        self.selected_repos_dict = {}  # type: dict[int, dict]
        self.repository_dict = {}  # type: dict[int, list[dict[str, Any]]]
        query_features_file = open(
            "mdi_thesis/query_features.json", encoding="utf-8")
        self.query_features = json.load(query_features_file)
        self.logger = get_logger(__name__)
        curr_path = Path(os.path.dirname(__file__))
        self.output_path = os.path.join(curr_path.parents[1],
                                        "outputs/data/", )
        self.filter_date = filter_date

    def select_repos(
        self,
        repo_nr: int,
        repo_list: List[int],
        query_parameters: str = ""
    ):
        """
        Select Repositories according to Parameters
        :param repo_nr: Number of queried repositories.
        :param language: Programming language of queried repositories.
        :param sort: Factor by which the repositories are sorted.
        :param repo_list: List with repositories if preselected
        :returns: List with dictionaries of selected repositories
        """
        selected_repos = []
        results_items = []
        if repo_nr < self.results_per_page:
            res_per_page = repo_nr
        else:
            res_per_page = self.results_per_page
        if repo_list:
            for item in repo_list:
                url = f"https://api.github.com/repos/{item}"
                self.logger.debug("url=%s", url)
                response = self.session.get(
                    url, headers=self.headers, timeout=100)
                results = response.json()
                while "next" in response.links.keys():
                    res = self.session.get(
                        response.links["next"]["url"], headers=self.headers
                    )
                    results.extend(res.json())
                selected_repos.append(results)
            self.selected_repos_dict = utils.clean_results(selected_repos)

        else:
            search_url = (
                "https://api.github.com/search/repositories?q="
                + query_parameters
                + "&access_token="
                + self.token
                + "&per_page="
                + str(res_per_page)
            )
            initial_search_url = (
                search_url
                + "&page=1"
            )
            self.logger.debug("Initial search query: %s", initial_search_url)

            results = []
            cleaned_results = {}
            while len(cleaned_results) < repo_nr:
                try:
                    response = self.session.get(
                        initial_search_url, headers=self.headers, timeout=100)
                    results = response.json()
                    if "items" in results:
                        results_items = results["items"]
                        if repo_nr <= 100:
                            selected_repos.extend(results_items)
                            break
                        if response.links.get('next'):
                            results = self.get_next_search_pages(
                                response=response,
                                results=results_items,
                                target_num=repo_nr)
                            selected_repos.extend(results)
                            cleaned_results = utils.clean_results(
                                selected_repos)

                        else:
                            continue
                    else:
                        continue
                except KeyError as key_err:
                    self.logger.error("Key error: %s", key_err)
                    time.sleep(10)
                else:
                    time.sleep(1)
            repo_counter = 0
            for repo, element in cleaned_results.items():
                self.selected_repos_dict[repo] = element
                repo_counter += 1
                if repo_counter == repo_nr:
                    break
                else:
                    response = self.session.get(
                        initial_search_url, headers=self.headers, timeout=100)
                    results = response.json()

    def check_rate_limit(self, response):
        """
        Checking rate limit and sleep for the
        required waiting time.
        :param response: Response to get required waiting time.
        """
        unix_time_to_reset = response.headers.get(
            "X-RateLimit-Reset")
        datetime_to_reset = datetime.fromtimestamp(int(unix_time_to_reset))
        time_till_rerun = abs(datetime_to_reset - datetime.now())
        minutes_till_rerun = math.ceil(
            (time_till_rerun.total_seconds()) / 60)
        self.logger.critical("API rate exceeded. Sleeping %s minutes.",
                             minutes_till_rerun)
        time.sleep(time_till_rerun.total_seconds())

    def get_next_search_pages(self, response, results, target_num):
        """
        Helper function for gathering next pages for search results.
        :param response: Response of first page
        :param results: Results returned by first response
        :param targe_num: Number of wanted results.
        """
        if 'next' in response.links:
            is_next = True
        else:
            is_next = False
        # is_next = response.links.get('next')
        while is_next:
            try:
                if 'next' in response.links:
                    next_url = response.links['next']['url']
                    self.logger.debug("Search query: %s",
                                      next_url)
                    response = self.session.get(next_url,
                                                headers=self.headers)
                    if response.status_code in [403, 429]:
                        self.logger.critical("Status code: %s",
                                             response.status_code)
                        self.check_rate_limit(response=response)
                        continue
                    elif response in [400, 401, 404, 406, 410]:
                        self.logger.critical("Status code: %s",
                                             response.status_code)
                        break
                    elif response.status_code in [500, 502, 503, 504]:
                        self.logger.critical("Status code: %s",
                                             response.status_code)
                        raise ConnectionError
                    elif response.status_code == 200:
                        if "items" in response.json():
                            next_result = response.json()["items"]
                            results.extend(next_result)
                else:
                    is_next = False
                if len(results) >= target_num:
                    is_next = False

            except KeyError as key_error:
                self.logger.error(
                    "Query failed: KeyError: %s at response status code: %s",
                    key_error, response.status_code)
                # is_next = False
                time.sleep(5)
                continue
        return results

    def query_repository(
        self,
        queried_features: List[str],
        filters: Dict[str, Any],
        updated_at_filt: bool = False,
        repo_list: Union[List[int], None] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Calls functions which perform actual query.
        :param queried_features: List with gathered features
        :return:
        """
        self.logger.info("Getting request information for feature(s): %s",
                         queried_features)
        feature_list = []  # type: list[str]
        query_dict = {}  # type: dict[str, list]

        if queried_features:
            for feature in queried_features:
                feature_list = (
                    self.query_features.get(feature).get("feature_list")
                )
                request_url_1 = (
                    self.query_features.get(feature).get("request_url_1")
                )
                request_url_2 = (
                    self.query_features.get(feature).get("request_url_2")
                )
                query_dict[feature] = [
                    feature_list, request_url_1, request_url_2]
        request_data_dict = {}
        for param, query in query_dict.items():
            if "organization_users" in queried_features:
                time.sleep(10)
            else:
                time.sleep(240)
            param_list = self.get_repository_data(
                feature_list=query[0],
                request_url_1=query[1],
                request_url_2=query[2],
                filters=filters,
                repo_list=repo_list,
                updated_at_filt=updated_at_filt
            )
            request_data_dict[param] = param_list

        return request_data_dict

    def get_single_object(self,
                          feature: str,
                          filters: Dict[str, Any],
                          output_format: str
                          ) -> Dict[int,
                                    List[Dict[int,
                                              List[Dict[str,
                                                        Any]]]]]:
        """
        Function to retrieve issues and the comments for each.
        Note: Issues also contain pull requests.
        :param feature: Feature that is to be queried (e.g. commits)
        :return: A dictionary with the repository id,
        its issue ids and the comments per issue.
        """
        request_url_1 = self.query_features.get(
            feature).get("request_url_1")
        request_url_2 = self.query_features.get(
            feature).get("request_url_2")
        request_url_3 = self.query_features.get(
            feature).get("request_url_3")
        try:
            filter_date = filters.get("since")
            if filter_date:
                filter_date = datetime.strptime(filter_date,
                                                '%Y-%m-%dT%H:%M:%SZ')
        except AttributeError:
            filter_date = None
        self.logger.info("Starting query for repository request...")

        objects_per_repo = self.query_repository(
            queried_features=[feature], filters=filters).get(
            feature
        )  # Object e.g. issue or commit
        self.logger.info("Finished query for repository request.")
        object_key = self.query_features.get(feature).get("feature_key")
        single_object_dict = {}
        subfeature_list = self.query_features.get(
            feature).get("subfeature_list")
        if isinstance(objects_per_repo, Dict):
            for repo_num, repository in enumerate(objects_per_repo, start=1):
                if repo_num % 100 == 0:
                    self.logger.info("Getting repo Nr. %s of %s",
                                     repo_num, len(objects_per_repo))
                if output_format.lower() == "dict":
                    object_storage = {}
                else:
                    object_storage = []
                url = request_url_1 + str(repository) + request_url_2
                objects = objects_per_repo.get(repository)
                object_counter = 0
                if objects:
                    for obj in objects:
                        object_counter += 1
                        if object_counter % 100 == 0:
                            self.logger.info(
                                "Get object Nr. %s of %s",
                                object_counter, len(objects))
                        object_id = obj.get(object_key)
                        if object_id:
                            self.logger.info(
                                "Starting querying subfeatures for object %s",
                                object_id)
                            comment_dict = self.get_subfeatures(
                                features=subfeature_list,
                                object_id=object_id,
                                object_url=url,
                                sub_url=request_url_3,
                                filter_date=filter_date
                            )
                        else:
                            comment_dict = {}
                        if isinstance(object_storage, Dict):
                            object_storage.update(comment_dict)
                        if isinstance(object_storage, List):
                            object_storage.append(comment_dict)

                    single_object_dict[repository] = object_storage

        else:
            single_object_dict = {}
        return single_object_dict

    def get_repository_data(
        self, feature_list: List[str], request_url_1: str,
        request_url_2: str, filters: Dict[str, Any],
        repo_list: Union[List[int], None],
        updated_at_filt: bool = False
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Query data from repositories
        :param feature_list: Features are the information,
         which should be stored
        after querying to avoid gathering unwanted data.
        :param request_url_1: First part of the url,
        split bc. in some cases
        information such as the repository id must be in the middle of the url.
        :param request_url_2: Second part of the url,
         pointing to the GitHub API subcategory.

        :return: Repository data of the selected features.
        """
        repository_dict = {}
        results = {}
        filter_str = ""
        if filters:
            for key, value in filters.items():
                filter_str = filter_str + key + "=" + value + "&"
        self.logger.info(
            "Getting repository data of %s repositories",
            len(self.selected_repos_dict)
        )
        if repo_list:
            objects = [repo for repo in repo_list if repo is not None]
        else:
            objects = self.selected_repos_dict
        one_year_ago = self.filter_date - relativedelta.relativedelta(years=1)
        for ind, object_id in enumerate(objects, start=1):
            if ind % 100 == 0:
                self.logger.info("Getting object Nr. %s of %s",
                                 ind, len(objects))
                time.sleep(10)
            complete_results = False
            while not complete_results:
                if not repo_list:
                    self.logger.info("Getting object %s", object_id)
                if request_url_2:
                    url_repo = str(request_url_1
                                   + str(object_id)
                                   + request_url_2)
                else:
                    url_repo = str(request_url_1 + str(object_id))
                if not repo_list:
                    self.logger.info("Getting page 1")
                start_url = (
                    str(url_repo) +
                    "?" +
                    str(filter_str) +
                    "per_page=" +
                    str(self.results_per_page) +
                    "&page=1"
                    )
                # if not repo_list:
                self.logger.info("Start URL: %s", start_url)
                try:
                    response = self.session.get(
                        start_url, headers=self.headers, timeout=100)
                    if response.status_code in [403, 429]:
                        self.logger.critical("Status code: %s",
                                             response.status_code)
                        self.check_rate_limit(response=response)
                    elif response in [400, 401, 404, 406, 410]:
                        self.logger.critical("Status code: %s",
                                             response.status_code)
                        self.logger.error("Query for repo %s failed: %s",
                                          object_id, response)
                        break
                    elif response.status_code in [500, 502, 503, 504]:
                        self.logger.critical("Status code: %s",
                                             response.status_code)
                        self.logger.debug("Connection failed at repo %s:%s",
                                          object_id, response)
                        raise ConnectionError
                    nr_of_pages = 1
                    if response.links.get("last"):
                        last = response.links.get("last")
                        if last:
                            last_url = last.get("url")
                            nr_of_pages = (
                                last_url.split("&page=", 1)[1]
                                )

                    self.logger.info("Querying total pages: %s", nr_of_pages)
                    results = response.json()
                    if response.status_code == 200 and nr_of_pages == 1:
                        complete_results = True
                        continue
                    next_link = response.links.get('next')
                    if next_link:
                        while next_link:
                            time.sleep(2)
                            try:
                                self.logger.debug("Search query: %s",
                                                  next_link.get("url"))
                                response = self.session.get(
                                    response.links['next']['url'],
                                    headers=self.headers)
                                next_link = response.links.get('next')
                                if response.status_code in [403, 429]:
                                    self.check_rate_limit(response=response)
                                elif response.status_code in [400, 401,
                                                              404, 406, 410]:
                                    self.logger.error(
                                        "Query object %s failed:%s",
                                        object_id, response)
                                    break
                                elif response.status_code in [500, 502,
                                                              503, 504]:
                                    self.logger.debug(
                                        "Connection failed at object %s:%s",
                                        object_id, response)
                                    raise ConnectionError
                                next_result = response.json()
                                results.extend(next_result)
                                if updated_at_filt:
                                    updated_at = next_result[-1].get(
                                        "updated_at")
                                    upd_date = datetime.strptime(
                                        updated_at,
                                        '%Y-%m-%dT%H:%M:%SZ').date()
                                    if one_year_ago > upd_date:
                                        complete_results = True
                                        break

                            except AttributeError as att_err:
                                self.logger.error(
                                    "Attribute error %s", att_err)
                                time.sleep(10)
                        complete_results = True
                        continue

                except AttributeError as att_error:
                    self.logger.error(
                        "Could not query Object:%s\nError: %s",
                        object_id, att_error)
                    self.logger.debug("Could not query results from Repo: %s \
                                      ...Retry in 5 minutes.", object_id)
                    complete_results = False
                    time.sleep(10)

            self.logger.info("Finished getting responses for all queries.")
            if repo_list:
                time.sleep(5)
            element_list = []  # element_list type: List[Dict[str, Any]]
            if isinstance(results, list):
                for element in results:
                    element_dict = {}  # element_dict type: Dict[str, Any]
                    if updated_at_filt:
                        updated_at = element.get("updated_at")
                        upd_date = datetime.strptime(
                            updated_at,
                            '%Y-%m-%dT%H:%M:%SZ').date()
                        if one_year_ago > upd_date:
                            continue
                    for feature in feature_list:
                        try:
                            element_dict[feature] = element.get(feature)
                        except AttributeError as att_error:
                            error_msg = (
                                "Encountered Attribute Error" +
                                str(att_error) +
                                "At element " +
                                feature +
                                "\t" +
                                element)
                            self.logger.error(error_msg)
                        continue
                    element_list.append(element_dict)

            elif isinstance(results, dict):
                element_dict = {}  # element_dict type: Dict[str, Any]
                for feature in feature_list:
                    element_dict[feature] = results.get(feature)
                element_list = element_dict  # [element_dict]
            repository_dict[object_id] = element_list

        self.logger.info("Done getting repository data.")
        return repository_dict

    def get_dependents(self, dependents_details: bool) -> Dict[int, int]:
        """
        Get dependencies of a repository
        :param keyword: Keyword to select either dependents or dependencies
        :return: Repository ids and the number of dependents or dependencies
        """
        dependents_results = {}
        repositories = self.selected_repos_dict.items()
        for repo_num, (repo, data) in enumerate(repositories, start=1):
            if repo_num % 100 == 0:
                self.logger.info("Getting repo Nr. %s of %s",
                                 repo_num,
                                 len(repositories))
                time.sleep(10)
            repo_name = data.get("name")
            repo_owner = data.get("owner")
            repo_owner_login = ""
            if repo_owner:
                repo_owner_login = repo_owner.get("login")
            self.logger.info("Getting repository %s", repo)
            url_1 = self.query_features.get("dependents").get("request_url_1")
            url_2 = self.query_features.get("dependents").get("request_url_2")
            url = url_1 + str(repo_owner_login) + "/" + str(repo_name) + url_2
            next_exists = True
            result_cnt = 500000
            total_dependents = 0
            visible_dependents = []
            options = None
            for run in range(5):
                try:
                    response = self.session.get(url)
                    soup = BeautifulSoup(response.content, "html.parser")
                    dependents_box = soup.find("div", {"id": "dependents"})
                    if dependents_box:
                        class_string = (
                            "select-menu.float-right.position-relative" +
                            ".details-reset.details-overlay"
                        )
                        if isinstance(dependents_box, BeautifulSoup):
                            menu = dependents_box.select(
                                "details",
                                {"class": class_string})
                            if menu:
                                options = menu[0].find_all(
                                    "div", {"class": "select-menu-list"})
                            break
                except HTTPError as hp_error:
                    self.logger.error("""
                                      Error %s at try %s.
                                      Retry in 1 minute.
                                      """, hp_error, run+1)
                    time.sleep(5)
                    continue

            if options:
                for row in options[0].find_all("a", href=True):
                    time.sleep(1)
                    href = ""
                    href_string = re.search(
                        r"href=\"(.+?)\"\s",  # Added r due to warning
                        str(row))
                    if href_string:
                        href = href_string.group(1)

                    self.logger.debug("Getting href %s", href)
                    pattern = "dependents?"
                    href_split = href.replace(pattern,
                                              f" {pattern} ").split(" ")
                    href_url = (url_1 +
                                href_split[0] +
                                href_split[1] +
                                "dependent_type=REPOSITORY&" +
                                href_split[2])
                    tmp_href_response = self.session.get(
                                href_url)
                    tmp_href_soup = BeautifulSoup(
                                tmp_href_response.content,
                                "html.parser")
                    box = tmp_href_soup.find(
                                "a", {"class": "btn-link selected"}
                                )
                    box_text = ""
                    if box:
                        box_text = box.text
                    dep_num = box_text.strip().split(" ")[0].replace(",", "")
                    try:
                        total_dependents += int(dep_num)
                    except ValueError:
                        self.logger.error(
                            "Could not add value %s from link %s",
                            dep_num, href_url)
                        time.sleep(3)
                    if dependents_details:
                        page_count = 0
                        if page_count % 10 == 0:
                            time.sleep(3)
                        while (next_exists
                                and len(visible_dependents) <
                                result_cnt):
                            page_count += 1
                            try:
                                dependents_box = tmp_href_soup.find(
                                    "div", {"id": "dependents"})
                                if not dependents_box:
                                    break
                                dependents = dependents_box.find(
                                    "div", {"class": "Box"})
                                dependents_elements = dependents.find_all(
                                    "div",
                                    {"class":
                                     "Box-row d-flex flex-items-center",
                                     "data-test-id": "dg-repo-pkg-dependent"})
                                if dependents_elements:
                                    for element in dependents_elements:
                                        cell = element.find(
                                            "span",
                                            {"class": "f5 color-fg-muted"})
                                        try:
                                            user = cell.find(
                                                "a",
                                                {"data-hovercard-type": "user"}
                                                ).text
                                        except AttributeError:
                                            user = cell.find(
                                                "a",
                                                {"data-hovercard-type":
                                                 "organization"}).text
                                        repository = element.find(
                                            "a",
                                            {"class":
                                             "text-bold",
                                             "data-hovercard-type":
                                             "repository"}).text
                                        visible_dependents.append(
                                            [user, repository])
                                else:
                                    break
                                selector = []
                                selector = dependents_box.find(
                                    "div", {"class": "BtnGroup"})
                                for u_elem in selector:
                                    if u_elem.text == "Next":
                                        next_exists = True
                                        if u_elem.find(href=True):
                                            href_url = u_elem["href"]
                                            self.logger.debug(
                                                "Getting page %s",
                                                href_url)
                                            page_count += 1
                                        else:
                                            self.logger.debug(
                                                "No next page found for %s",
                                                href_url
                                            )
                                            next_exists = False
                                    else:
                                        next_exists = False
                            except requests.exceptions.ConnectionError:
                                continue
            dependents_results[repo] = {"total_dependents":
                                        total_dependents,
                                        "visible_dependents":
                                        visible_dependents}
        return dependents_results

    def get_dependencies(self) -> Dict[int, int]:
        """
        NOTE: Dependency graph from GitHub is still in progress!
        Changes in near future can cause errors!
        Get dependencies of a repository.
        :return: Repository ids and the number of dependencies
        """
        dependency_results = {}
        repositories = self.selected_repos_dict.items()
        for repo_num, (repo, data) in enumerate(repositories, start=1):
            if repo_num % 100 == 0:
                self.logger.info("Getting repo Nr. %s of %s",
                                 repo_num,
                                 len(repositories))
            repo_name = data.get("name")
            repo_owner = data.get("owner")
            repo_owner_login = ""
            if repo_owner:
                repo_owner_login = repo_owner.get("login")
            self.logger.info("Getting repository %s", repo)
            url_1 = self.query_features.get(
                "dependencies").get("request_url_1")
            url_2 = self.query_features.get(
                "dependencies").get("request_url_2")
            url = url_1 + str(repo_owner_login) + "/" + str(repo_name) + url_2
            self.logger.debug("Getting url: %s", url)
            next_exists = True
            result_cnt = 500000
            results = set()
            dependencies = None
            page_count = 0
            while next_exists and len(results) < result_cnt:
                page_count += 1
                if page_count % 100 == 0:
                    time.sleep(5)
                dependencies_box = BeautifulSoup()
                soup = BeautifulSoup()
                for run in range(5):
                    try:
                        response = self.session.get(url)
                        soup = BeautifulSoup(response.content, "html.parser")
                        dependencies_box = soup.find(
                            "div", {"id": "dependencies"})
                        dependencies = dependencies_box.find(
                            "div", {"class": "Box",
                                    "data-view-component": "true"})
                        if dependencies_box:
                            break
                        else:
                            self.logger.error("""
                                            Could not find dependency
                                            box at %s try.
                                            Retry in 1 minute.
                                            """, run + 1)
                            time.sleep(3)
                            continue
                    except AttributeError:
                        self.logger.error(
                            "Attribute Error at repo_num %s, repo_id = %s in: \
                                %s",
                            repo_num, repo, dependencies_box)
                        time.sleep(5)
                if dependencies:
                    for element in dependencies.find_all(
                        "li", {"class": "Box-row",
                               "data-view-component": "true"}):
                        # time.sleep(1)
                        try:
                            text = element.find(
                                "a", {"class": "h4 Link--primary no-underline"}
                                ).text.strip()
                        except AttributeError:
                            text = element.find(
                                "div", {"class": "d-flex flex-items-baseline"}
                                ).text.strip()
                        results.add(text)
                else:
                    self.logger.debug("No dependencies for repo %s",
                                      repo)
                    break
                next_exists = False
                try:
                    paginate_cont = soup.find("div",
                                              {"class": "paginate-container"})
                    if paginate_cont:
                        for u in paginate_cont.find_all('a'):
                            if u.text == "Next":
                                next_exists = True
                                url = url_1 + u["href"]
                                self.logger.debug("Getting page %s", url)
                    else:
                        self.logger.debug("Could not retrieve page %s", url)
                        time.sleep(3)

                except HTTPError as hp_error:
                    self.logger.error(hp_error)
                    next_exists = True
            dependency_results[repo] = sorted(results)
        return dependency_results
    
    def get_branches(self, activity: str = "all") -> Dict[int, Dict[str, str]]:
        """
        Gets all branches from GitHub page instead of API.
        :return: Branch name and corresponding status
        """
        branches_results = {}
        repositories = self.selected_repos_dict.items()
        for repo_num, (repo, data) in enumerate(repositories, start=1):
            if repo_num % 100 == 0:
                self.logger.info("Getting repo Nr. %s of %s",
                                 repo_num,
                                 len(repositories))
            repo_name = data.get("name")

            repo_owner = data.get("owner")
            repo_owner_login = ""
            if repo_owner:
                repo_owner_login = repo_owner.get("login")
            self.logger.info("Getting repository %s", repo)
            url_1 = self.query_features.get(
                "branches_web").get("request_url_1")
            url_2 = self.query_features.get(
                "branches_web").get("request_url_2")

            url = (url_1 +
                   str(repo_owner_login) +
                   "/" +
                   str(repo_name) +
                   url_2 +
                   ("/") +
                   activity
                   )
            next_exists = True
            result_cnt = 500000
            results = {}
            while next_exists and len(results) < result_cnt:
                response = self.session.get(url)
                soup = BeautifulSoup(response.content, "html.parser")
                all_branches = soup.find("div", {"data-target":
                                                 "branch-filter.result"})
                time.sleep(1)
                if all_branches:
                    for element in all_branches.find_all(
                        "li",
                        {"class": "Box-row position-relative"}):
                        branch_name = ""
                        branch_status = ""
                        element = element.find("branch-filter-item")
                        try:
                            branch_name = element.select(
                                'a[class*="branch-name"]')[0].text
                            if element.select('span[class*="State State"]'):
                                branch_status = element.select(
                                    'span[class*="State State"]'
                                    )[0].text.strip()
                            elif element.select('a[class*="btn "]'):
                                branch_status = element.select(
                                    'a[class*="btn "]')[0].text.strip()
                            else:
                                branch_status = ""
                        except AttributeError:
                            self.logger.error(AttributeError)
                        results[branch_name] = branch_status
                else:
                    break
                next_exists = False
                try:
                    for u_elem in soup.find(
                        "div", {"class": "paginate-container"}).find_all('a'):
                        if u_elem.text == "Next":
                            next_exists = True
                            url = u_elem["href"]
                except HTTPError as hp_error:
                    self.logger.info(hp_error)
                    time.sleep(1)
                    next_exists = True
            branches_results[repo] = results
            time.sleep(1)
        return branches_results

    def get_context_information(self, main_feature: str,
                                sub_feature: str, filters: Dict[str, Any]
                                ) -> Dict[int, List[Dict[str, Any]]]:
        """
        :param main_feature: Feature which concerns the main information.
        :param sub_feature: Feature which concerns the context information.
        :return: Dictionary with context information of main feature.
        """
        main_data = self.query_repository([main_feature], filters=filters)
        request_url_1 = self.query_features.get(
            sub_feature).get("request_url_1")
        request_url_2 = self.query_features.get(
            sub_feature).get("request_url_2")
        feature_list = self.query_features.get(
            sub_feature).get("feature_list")
        feature_key = self.query_features.get(
            sub_feature).get("feature_key")
        return_data = {}
        feature_data = main_data.get(main_feature)
        repositories = {}
        if isinstance(feature_data, Dict):
            repositories = feature_data.items()
        for repo_num, (repo, data) in enumerate(repositories, start=1):
            if repo_num % 100 == 0:
                self.logger.info("Getting repo Nr. %s of %s",
                                 repo_num,
                                 len(repositories))
            data_list = []
            for element in data:
                element_dict = {}
                key = element.get(feature_key)
                element_url = request_url_1 + str(key) + request_url_2
                result = self.session.get(
                            element_url, headers=self.headers, timeout=100)
                sub_data = result.json()
                for feature in feature_list:
                    if isinstance(sub_data, dict):
                        element_dict[feature] = sub_data.get(feature)
                    else:
                        element_dict[feature] = sub_data
                data_list.append(element_dict)
            return_data[repo] = data_list
            time.sleep(1)
        return return_data

    def get_subfeatures(
        self,
        features: List[str],
        object_id: int,
        object_url: str,
        sub_url: str,
        filter_date: Union[datetime, None]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        :param session: Active request session
        :param headers: Headers for query with active session
        :param features: Which features are queried from GitHub
        :param object_id: Object ID,
        from which the concerning comments are queryied (e.g. pull, issue)
        :param object_url:
        Base url to which the object id is added to query the information.
        :param sub_url: Sub url referring to the subfeatures of a certain
        information (e.g. comments as subfeatures for issues as features)
        :return: Dictionary with the object id and the concerning comments
        """
        subfeature_dict = {}
        url = object_url + "/" + str(object_id) + sub_url
        url_param = "?per_page=100&page=1"
        start_url = url + url_param
        self.logger.info("Getting page %s", start_url)
        response = self.session.get(start_url,
                                    headers=self.headers,
                                    timeout=100)
        results = response.json()
        if response.links.get('next'):
            while response.links.get('next'):
                try:
                    url = response.links['next']['url']
                    self.logger.debug("Search query: %s",
                                      url)
                    response = self.session.get(
                        url,
                        headers=self.headers)
                    time.sleep(1)
                    if response.status_code in [403, 429]:
                        self.check_rate_limit(response=response)
                    elif response.status_code in [400, 401,
                                                  404, 406, 410]:
                        self.logger.error(
                            "Query object %s failed:%s",
                            object_id, response)
                        break
                    elif response.status_code in [500, 502,
                                                  503, 504]:
                        self.logger.debug(
                            "Connection failed at object %s:%s",
                            object_id, response)
                        raise ConnectionError
                    next_result = response.json()
                    if isinstance(results, List):
                        results.extend(next_result)
                    elif isinstance(results, Dict):
                        results.update(next_result)
                        
                except HTTPError as hp_error:
                    self.logger.error(
                        "Error at querying all pages %s", hp_error)
                    time.sleep(10)

        element_dict = {}  # type: dict[str, Any]
        subfeature_list = []
        if isinstance(results, list):
            for element in results:
                element_dict = {}
                for feature in features:
                    if filter_date:
                        if element.get("created_at"):
                            created_at = datetime.strptime(
                                element.get("created_at"),
                                '%Y-%m-%dT%H:%M:%SZ')
                            if created_at > filter_date:
                                element_dict[feature] = element.get(feature)
                    else:
                        element_dict[feature] = element.get(feature)
                subfeature_list.append(element_dict)
            subfeature_dict[object_id] = subfeature_list

        elif isinstance(results, dict):
            for feature in features:
                if filter_date:
                    created_at = results.get("created_at")
                    if created_at:
                        created_at = datetime.strptime(
                            created_at,
                            '%Y-%m-%dT%H:%M:%SZ')
                        if created_at > filter_date:
                            element_dict[feature] = results.get(feature)
                else:
                    element_dict[feature] = results.get(feature)
                # element_dict[feature] = results.get(feature)
            subfeature_list.append(element_dict)
            subfeature_dict[object_id] = subfeature_list
        else:
            subfeature_dict[object_id] = []
        return subfeature_dict

    def __del__(self):
        self.session.close()
