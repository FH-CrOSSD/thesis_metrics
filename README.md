# thesis_metrics

This repository is a fork of the [MDI Thesis](https://github.com/JacquelineSchmatz/MDI_Thesis) repository by Jacqueline Schmatz, which is part of her master thesis.
We made some modifications to integrate it better into our own project and updated some crawling features according to GitHub website changes.

This repository is part of the [CrOSSD](https://health.crossd.tech/about) project and powers the `bak-rest-drone` component.  
**See our main repository [here](https://github.com/FH-CrOSSD/crossd).**

## Acknowledgements

The financial support from Internetstiftung/Netidee is gratefully acknowledged. The mission of Netidee is to support development of open-source tools for more accessible and versatile use of the Internet in Austria.

___

## Original README
### MDI Thesis - Schmatz Jacqueline

### Description
The provided python scripts represent two pipelines, one to collect required data, and another to calculate the metrics. For the python scripts and the jupyter notebooks are used different environments, thus the requirements are stored seperately.

- `requirements.txt` - Requirements for py scripts
- `analysis_requirements.txt` - Requirements for Jupyter Notebooks
#### File Structure
The mdi_thesis folder contains the scripts for data collection and metrics calculation. The files and their purpose are listed below respectively:

##### Scripts:

* `base_data_miner.py` - Runs the data collection processes and passes filter data parameter. Stores gathered data in json files.
* `metrics_pipeline.py` - Reads the stored json files and calculates all metrics by reading the metrics and defined information and date filters from `metrics_data_mapping.json`. The metric names are used to call the corresponding function name from the `metrics.py` file. The pipeline requires a data parameter, this parameter is used to get the corresponding date range for which a metric is calculated.
* `metrics.py` - Includes all functions for calculating the metrics. Each function requires the corresponding data in form of a dictionary.
* `external.py` - Includes functions utilized for other data sources than the GitHub API or GitHub project's website directly. This includes for instance the NVD database.


##### base/Scripts:
* `base.py` - Includes all functionalities required to gather data either with the GitHub API or directly from the project's website with a web scraper. Handles pagination and API rate exceed limits. 
* `utils.py` - Holds helper function for instance for writing and reading json files.
##### Files:
- `criticality_score_weights.json` - The metric criticality score takes weights as inputs for calculation, thus for each parameter a weight value is stored in this file. Can be adapted if required. 
- `metrics_data_mapping.json` - For each metric function included in the `metrics.py` an entry is present in this json with the corresponding required information and the filter parameters for the selected time period. For instance the metric contributions_distributions include commits as information, and montsh=1 as the time parameter for which the metric is calculated. 

##### Notebooks:

- `Results_analysis.ipynb` - Includes the investigation of all metrics results.
- `data_check.ipynb` - Used for a quick check the completeness of the data. For more details the date range included for each metric and the corresponding information is stored in a seperate file. 


### Security
Currently a GitHub token is required, to achieve this create a GitHub token and copy it into the constants_template.py file.
Then rename the file to constants.py.

### Contributions

The calculation of the criticality score is based on the formula provided by [ossf/criticality_score ](https://github.com/ossf/criticality_score).
Further this project is used for a Master thesis in cooperation with the [CrOSSD Project](https://crossd.tech/)

