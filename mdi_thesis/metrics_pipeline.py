"""
Metrics pipeline

Author: Jacqueline Schmatz
Description: Calculates all metrics
"""

# Imports
import json
import os
import sys
import inspect
from pathlib import Path
from typing import Dict, List
from datetime import date, datetime
from dateutil import relativedelta
import mdi_thesis.base.base as base
import mdi_thesis.base.utils as utils
import mdi_thesis.metrics as metrics


class MetricsPipeline:
    """
    Pipeline which reads data, calculates metrics and stores the
    results in json files.
    """

    def __init__(self, filter_date: date):
        self.logger = base.get_logger(__name__)
        self.results_dict = {}
        self.languages = set()
        self.data_dict = self.read_json()
        self.filter_date = filter_date
        curr_path = Path(os.path.dirname(__file__))
        metrics_objective_mapping = open(
            os.path.join(curr_path, "metrics_data_mapping.json"),
            encoding="utf-8",
        )
        self.metrics_objective_mapping = json.load(metrics_objective_mapping)
        self.metric_periods = {}
        self.metric_objective_periods = {}

        parent_dir = os.path.abspath(".")
        if parent_dir not in sys.path:
            sys.path.append(parent_dir)
        self.output_path = os.path.join(parent_dir, "outputs", "results")

    def read_json(self):
        """
        Reads all json files returned by base_data_miner.py
        Stores results in dictionary by objective and language.
        """
        # parent_dir = os.path.abspath(".")
        parent_dir = Path(os.path.dirname(__file__))
        # if parent_dir not in sys.path:
        #     sys.path.append(parent_dir[0])
        combined_dict = {}
        path = os.path.join(parent_dir.parents[0], "outputs", "data")
        # path = os.path.join(parent_dir, "outputs", "data")
        self.logger.info("Reading json files from path %s", path)
        for filename in os.listdir(path):
            if filename.endswith(".json"):
                objective = filename.split(".")[0].split("_", 1)[1]
                language = filename.split("_")[0]
                self.languages.add(language)
                file_path = os.path.join(path, filename)
                tmp_dict = utils.json_to_dict(path=file_path)
                lang_dict = {}
                lang_dict[language] = tmp_dict
                if objective in combined_dict:
                    combined_dict[objective].update(lang_dict)
                else:
                    combined_dict[objective] = lang_dict
        return combined_dict

    def filter_data(self, data: Dict, filter_parameter: str, filter_period: str):
        """
        Filters data according to parameter.
        :param data: Data to be filtered
        :param filter_parameter: Parameter of GitHub object
        on which the filter is applied.
        :param filter_period: Filter period for which the object
        is filtered.
        """
        self.logger.info(
            "Filtering data by Parameter: %s and Period %s",
            filter_parameter,
            filter_period,
        )
        filtered_data = {}
        filter_period = filter_period.split("=")
        attributes = {str(filter_period[0]): int(filter_period[1])}
        filter_start_date = self.filter_date - relativedelta.relativedelta(**attributes)
        # filter_start_date = (
        #     self.filter_date -
        #     relativedelta.relativedelta(filter_period))
        if isinstance(filter_start_date, datetime):
            filter_start_date = filter_start_date.date()
        self.logger.debug("Filter start date: %s", filter_start_date)
        self.logger.debug("Filter end date: %s", self.filter_date)
        date_range = []
        for repo, content in data.items():
            content_filt = None
            if isinstance(content, List):
                content_filt = []
                for element in content:
                    element_date = element.get(filter_parameter)
                    if element_date:
                        element_date = datetime.strptime(
                            element_date, "%Y-%m-%dT%H:%M:%SZ"
                        )
                        if isinstance(element_date, datetime):
                            element_date = element_date.date()
                        # if filter_start_date > element_date:
                        #     content_filt.append(element)
                        if (
                            filter_start_date <= element_date
                            and element_date <= self.filter_date
                        ):
                            date_range.append(element_date)
                            content_filt.append(element)
                    else:
                        commit = element.get("commit")
                        author = commit.get("author")
                        element_date = author.get("date")
                        if element_date:
                            element_date = datetime.strptime(
                                element_date, "%Y-%m-%dT%H:%M:%SZ"
                            )
                            if isinstance(element_date, datetime):
                                element_date = element_date.date()
                                # if filter_start_date > element_date:
                                #     content_filt.append(element)
                                if (
                                    filter_start_date <= element_date
                                    and element_date <= self.filter_date
                                ):
                                    date_range.append(element_date)
                                    content_filt.append(element)

            if isinstance(content, Dict):
                content_filt = {}
                for element_id, element in content.items():
                    if isinstance(element, Dict):
                        element_date = element.get(filter_parameter)
                        if element_date:
                            element_date = datetime.strptime(
                                element_date, "%Y-%m-%dT%H:%M:%SZ"
                            )
                            if isinstance(element_date, datetime):
                                element_date = element_date.date()
                            if (
                                filter_start_date <= element_date
                                and element_date <= self.filter_date
                            ):
                                content_filt[element_id] = element
                                date_range.append(element_date)
                        else:
                            commit = element.get("commit")
                            if commit:
                                author = commit.get("author")
                                element_date = author.get("date")
                                if element_date:
                                    element_date = datetime.strptime(
                                        element_date, "%Y-%m-%dT%H:%M:%SZ"
                                    )
                                    if isinstance(element_date, datetime):
                                        element_date = element_date.date()
                                    if (
                                        filter_start_date <= element_date
                                        and element_date <= self.filter_date
                                    ):
                                        content_filt[element_id] = element
                                        date_range.append(element_date)
                    elif isinstance(element, List):
                        for elem in element:
                            element_date = elem.get(filter_parameter)
                            if element_date:
                                element_date = datetime.strptime(
                                    element_date, "%Y-%m-%dT%H:%M:%SZ"
                                )
                                if isinstance(element_date, datetime):
                                    element_date = element_date.date()
                                if (
                                    filter_start_date <= element_date
                                    and element_date <= self.filter_date
                                ):
                                    content_filt[element_id] = element
                                    date_range.append(element_date)
                            else:
                                commit = elem.get("commit")
                                if commit:
                                    author = commit.get("author")
                                    element_date = author.get("date")
                                    if element_date:
                                        element_date = datetime.strptime(
                                            element_date, "%Y-%m-%dT%H:%M:%SZ"
                                        )
                                        if isinstance(element_date, datetime):
                                            element_date = element_date.date()
                                        if (
                                            filter_start_date <= element_date
                                            and element_date <= self.filter_date
                                        ):
                                            content_filt[element_id] = element
                                            date_range.append(element_date)
            filtered_data[repo] = content_filt
        if date_range:
            min_date = min(date_range)
            max_date = max(date_range)
            date_diff = (max_date - min_date).days
            min_date = min_date.strftime("%Y-%m-%d")
            max_date = max_date.strftime("%Y-%m-%d")
        else:
            min_date = None
            max_date = None
            date_diff = None

        self.metric_periods["min_date"] = min_date
        self.metric_periods["max_date"] = max_date
        self.metric_periods["date_diff_days"] = date_diff

        return filtered_data

    def prep_data(self, language: str, objectives: Dict):
        """
        Collects required data of one language and multiple objectives.
        :param language: Programming language
        :param objectives: List with required objectives.
        """

        prep_data = {}
        for objective, filters in objectives.items():
            self.metric_periods = {}
            self.logger.info(
                "Data Preparation for %s and objective %s", language, objective
            )
            objective_dict = {}
            if objective in self.data_dict:
                objective_dict = self.data_dict.get(objective)
            else:
                self.logger.critical("No dictionary found for %s", objective)
            data_dict = {}
            if objective_dict:
                data_dict = objective_dict.get(language)
                if data_dict:
                    if filters:
                        param = filters[0]
                        period = filters[1]
                        self.logger.debug(
                            "Filtering objective %s for language %s",
                            objective,
                            language,
                        )
                        filtered_data = self.filter_data(
                            data=data_dict, filter_parameter=param, filter_period=period
                        )
                        prep_data[objective] = filtered_data
                        self.logger.debug(
                            "Adding dict %s - to objective %s",
                            self.metric_periods,
                            objective,
                        )
                    else:
                        self.logger.debug("Getting objective %s", objective)
                        prep_data[objective] = data_dict
                    self.metric_objective_periods[objective] = self.metric_periods
        return prep_data

    def run_metrics_to_json(self):
        """
        Run metric functions and store results in json files.
        """
        self.logger.info("Starting calculating metrics to json files.")
        metric_period_results = {}
        metric_period_languages = {}
        for lang in self.languages:
            self.logger.debug("Getting language %s", lang)
            metrics_results = {}
            for metric, objectives in self.metrics_objective_mapping.items():
                self.metric_objective_periods = {}
                try:
                    self.logger.info("Getting metric %s", metric)
                    data = self.prep_data(language=lang, objectives=objectives)
                    function_path = getattr(metrics, metric)
                    function_args = str(inspect.signature(function_path))
                    self.logger.debug(
                        "Function path: %s - Function args: %s",
                        function_path,
                        function_args,
                    )
                    metric_return = {}
                    if data:
                        if "filter_date" in function_args:
                            metric_return = function_path(
                                base_data=data,
                                filter_date=self.filter_date,
                                log=self.logger,
                            )
                        else:
                            self.logger.debug("Calculating metric %s", metric)
                            metric_return = function_path(
                                base_data=data, log=self.logger
                            )
                    else:
                        self.logger.critical("No data for metric %s", metric)
                    metrics_results[metric] = metric_return
                    metric_period_results[metric] = self.metric_objective_periods
                except AttributeError as att_err:
                    self.logger.error("Attribute Error: %s\n", att_err)
                    raise
            utils.dict_to_json(
                data=metrics_results,
                data_path=self.output_path,
                feature=lang + "_metrics",
            )
            metric_period_languages[lang] = metric_period_results
            self.results_dict[lang] = metrics_results
        curr_path = Path(os.path.dirname(__file__))
        output_path = os.path.join(
            curr_path.parents[0],
            "outputs/results/",
        )
        utils.dict_to_json(
            data=metric_period_languages,
            data_path=output_path,
            feature="metric_date_ranges",
        )


def run_pipeline(start_date: date):
    """
    Run pipeline.
    """
    pipeline = MetricsPipeline(filter_date=start_date)
    pipeline.run_metrics_to_json()


def main():
    """
    Set start for pipeline filters
    """

    start_date = date(2023, 8, 23)
    run_pipeline(start_date=start_date)


if __name__ == "__main__":
    main()
