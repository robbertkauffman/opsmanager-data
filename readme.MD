# Ops Manager Cluster & Metrics Script
This script will download cluster data and metrics from Ops Manager via APIs.

## Requirements
To run you need Python 3.x. You also need the 
[requests library](http://docs.python-requests.org/en/master/user/install/#install). 
You can install this via the command line when you have Python installed:
```bash
  $ pip3 install requests
```

## Usage
1. Open Ops Manager in your browser and login. Make sure that the user you're
logging in with has read access to all orgs and projects.
2. Note the base URL (host) of Ops Manager in your browser. This is everything 
that comes before the first '/', e.g. `https://acme-corp.com:8080`
3. Get the value of the Ops Manager authentication cookie `mmsa-hosted`, e.g.
`7135ba929465c2e36bc129e8c01efef4-20230131`. You can view cookies in your 
browser's Developer Console or via the *i* icon next to the URL in Chrome. 
4. Run the following command in the folder that contains the `getdata.py` script:
```bash
  $ python getdata.py BASEURL AUTHCOOKIE
```

If successful, it will save a CSV file containing the cluster data, and a 
bunch of JSON files containing the metrics.

If you get any 403 errors, check if you are using the correct BASEURL or 
AUTHCOOKIE.

## Sample output
| cluster_id | replica_set_id | name     | host_id | replica_state | cpu | ram_mb  | wt_cache_size_gb | version |
| ---------- | -------------- | -------- | ------- | ------------- | --- | ------- | ---------------- | ------- |
| 63d...     | TestRS         | TestRS_7 | cee...  | PRIMARY       | 2   | 3816    | 0.25             | 4.2.23  |
| 63d...     | TestRS         | TestRS_8 | 08d...  | SECONDARY     | 2   | 3816    | 0.25             | 4.2.23  |
| 63d...     | TestRS         | TestRS_9 | 6bd...  | SECONDARY     | 2   | 3816    | 0.25             | 4.2.23  |

For sample output of the metrics, please see the [sample-metrics.json](sample-metrics.json) file.