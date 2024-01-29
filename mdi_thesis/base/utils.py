"""
Module for helper functions for data collection,
data cleaning and data storage.
"""
import json
import os
import re

# import numpy as np
from typing import Dict, List, Any, Union


# class npEncoder(json.JSONEncoder):
#     def default(self, obj):
#         if isinstance(obj, np.int32):
#             return int(obj)
#         return json.JSONEncoder.default(self, obj)


def __get_ids_from_txt__(path: str) -> List[int]:
    with open(path, encoding="utf-8") as file:
        lines = file.read().splitlines()
        ids = [int(i) for i in lines]
        return ids


def invert_dict(dictionary: Dict):
    """
    Change dictionary values to keys.
    """
    inverse = dict()
    for key in dictionary:
        for item in dictionary[key]:
            if item not in inverse:
                inverse[item] = [key]
            else:
                inverse[item].append(key)
    return inverse


def clean_results(
    results: List[Any],
) -> Dict[int, Dict[str, Any]]:
    """
    Removes unwanted information from the queried repository data.
    :param results: Results to be clean in dictionary form
    :param key_list: List of keys to be taken
    :returns: dictionary with clean lists
    """
    dictionary_of_list = {}
    key_list = ["id", "node_id", "name", "owner", "html_url"]
    item_counter = 0
    test_dict = {}
    for item in results:
        if "id" in item:
            item_counter += 1
            repo_id = item["id"]
            repo_name = item["name"]
            repo_owner = item["owner"]
            selected_items = {k: v for k, v in item.items() if k in key_list}
            test_dict[repo_id] = [item_counter, repo_name, repo_owner]
            dictionary_of_list[repo_id] = selected_items
    return dictionary_of_list


def get_contributors(contributors_data, check_contrib=False) -> Dict[int, int]:
    """
    Gets number of contributors.
    :param contributors_data: Data with user and their contributions
    :param check_contrib: True if for contributions has to be checked
    :return: Number of contributors per repository
    """
    repo_contributors = {}
    for repo, data in contributors_data.items():
        contributors_nr = 0
        if check_contrib:
            for user in data:
                if user and isinstance(user, dict):
                    contributions = user.get("contributions")
                    if contributions:
                        contributors_nr += 1
        else:
            contributors_nr = len(data)
        repo_contributors[repo] = contributors_nr
    return repo_contributors


def get_contributor_per_files(commit: Dict) -> Dict[str, set]:
    """
    Getting unique contributors per file and
    retrieving co authors from the commit message.
    :param commit: Single Commit object returned by API
    :return: Files with corresponding contributors
    """
    file_committer = {}
    for features in commit.values():
        for row in features:
            files = row.get("files")
            try:
                co_authors = set()
                committer_email = row.get("commit").get("committer").get("email")
                author_email = row.get("commit").get("author").get("email")
                message = row.get("commit").get("message")
                co_author_line = re.findall(r"Co-authored-by:(.*?)>", message)
                verification = row.get("commit").get("verification").get("verified")
                for value in co_author_line:
                    co_author = value.split("<")[-1]
                    co_authors.add(co_author)
                if committer_email != author_email:
                    contributor = author_email
                else:
                    if verification:
                        contributor = author_email
                    else:
                        contributor = committer_email
            except AttributeError as att_err:
                print(f"Attribute error at commit: {commit}: {att_err}")
                raise
            if co_authors:
                contributors = {contributor} | co_authors
            else:
                contributors = {contributor}
            for file in files:
                filename = file.get("filename")
                if filename not in file_committer:
                    file_committer[filename] = contributors
                else:
                    existing_file = file_committer.get(filename)
                    if existing_file:
                        file_committer[filename] = existing_file.union(contributors)
    return file_committer


def dict_to_json(data: Union[Dict, List], data_path: str, feature: str):
    """
    Helper function to write file.
    :param data: data to be written
    :param data_path: Path where file should be written.
    :param feature: Feature for filename.
    """
    # json_object = json.dumps(data, indent=4, cls=npEncoder)
    json_object = json.dumps(data, indent=4)
    file_name = os.path.join(data_path, (feature + ".json"))
    with open(file_name, "w", encoding="utf-8") as outfile:
        outfile.write(json_object)


def json_to_dict(path: str) -> Dict:
    """
    Helper function
    :param path: Path to json file
    :return: dictionary with json content
    """
    with open(path, encoding="utf-8") as json_file:
        data = json.load(json_file)
    return data
