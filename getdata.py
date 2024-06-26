from argparse import ArgumentParser
import csv
import json
import os
import requests
import sys

DEFAULT_BASE_URL = "https://cloud.mongodb.com"
ORGS_URL = "{}/settings/orgs"
GROUPS_URL = "{}/orgs/{}/groups"
SERVER_URL = "{}/servers/list/{}?mapAutomationAgents=true&mapBackupAgents=true&mapMonitoringAgents=true&mapProcesses=true"
METRICS_URL = "{}/metrics/v1/groups/{}/hosts/{}/replicaset?retention={}"
CONFIG_DB_URL = "{}/metrics/v1/groups/{}/hosts/{}/databases/storage?retention={}&bucketed=false&databaseName=config"
RETENTION_METRICS = ["172800000"] # 48 hours or 1 week (604800000)
RETENTION_CONFIG_DB = "3600000" # 1 hour

def main(orgs):
  with open('clusters.csv', 'w', newline='') as csvfile:
    fieldnames = ['cluster_id', 'replica_set_id', 'name', 'host_id', 'replica_state', 'cpu', 'ram_mb', 'wt_cache_size_gb', 'version']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    
    if not orgs:
      orgs = get_orgs()
    
    for org_id in orgs:
      makedirs(org_id)
      projects = get_projects(org_id)
      for project in projects:
        if project['id'] in PROJECT_FILTER:
          project_id = project['id']
          makedirs(org_id + '/' + project_id)
          servers = get_servers(org_id, project_id)
          hosts = save_servers_and_get_hosts(servers, writer)
          for host in hosts:
            cluster_id = host[0]
            host_id = host[1]
            for retention in RETENTION_METRICS:
              # download cluster metrics
              download_metrics(org_id, project_id, cluster_id, host_id, retention, "-metrics-" + retention)
            # download config db metrics
            # download_metrics(org_id, project_id, cluster_id, host_id, RETENTION_CONFIG_DB, "-configdb")
      print(f"Processed org {org_id}")
    print("Successfully downloaded all cluster data and metrics!")

def get_orgs():
  url = ORGS_URL.format(BASE_URL)
  resp = requests.get(url, headers=HEADERS, verify=NO_VERIFY)
  if resp.ok:
    org_ids = []
    orgs = get_prop(resp.json(), 'orgs')
    if orgs:
      for org in orgs:
        if 'id' in org:
          org_ids.append(org['id'])
    return org_ids
  else:
    exit_on_bad_response(resp)

def get_projects(org_id):
  url = GROUPS_URL.format(BASE_URL, org_id)
  resp = requests.get(url, headers=HEADERS, verify=NO_VERIFY)
  if resp.ok:
    return resp.json()
  else:
    exit_on_bad_response(resp)

def get_servers(org_id, project_id):
  url = SERVER_URL.format(BASE_URL, project_id)
  resp = requests.get(url, headers=HEADERS, verify=NO_VERIFY)
  if resp.ok:
    servers_json = resp.json()
    with open(f'{org_id}/servers-{project_id}.json', 'w') as fp:
      json.dump(servers_json, fp)
    return servers_json
  else:
    exit_on_bad_response(resp)

def save_servers_and_get_hosts(servers, writer):
  hosts = []
  for server in servers:
    processes = get_prop(server, 'processes')
    if processes and len(processes) > 0:
      for process in processes:
        state = get_prop(process, 'state')
        process_type = get_prop(process, 'processType')
        is_conf = get_prop(state, 'isConf')
        last_ping = get_prop(state, 'lastPing')
        if process_type == 'mongod' and is_conf == False and last_ping != 0:
          # use user alias as cluster name on Atlas
          if BASE_URL != DEFAULT_BASE_URL:
            name = get_prop(process, 'name')
          else:
            name = get_prop(state, 'userAlias')
          cluster_id = get_prop(state, 'parentClusterId')
          replica_set_id = get_prop(state, 'replicaSetId')
          if in_filter_startswith(name, CLUSTER_FILTER):
            host_id = get_prop(state, 'hostId')
            replica_state = get_prop(state, 'replicaState')
            # hostname = process['hostname']
            cpu = get_prop(state, 'hostInfo.Cores')
            ram_mb = get_prop(state, 'hostInfo.RAM (MB)')
            wt_cache_size_gb = get_prop(process, 'args2_6.storage.wiredTiger.engineConfig.cacheSizeGB')
            version = get_prop(state, 'version')
            hosts.append((cluster_id, host_id))
            
            writer.writerow({'cluster_id': cluster_id, 'replica_set_id': replica_set_id, 'name': name, 'host_id': host_id, 'replica_state': replica_state, 'cpu': cpu, 'ram_mb': ram_mb, 'wt_cache_size_gb': wt_cache_size_gb, 'version': version})
  return hosts

def get_prop(obj, prop):
  if obj is None:
    return obj

  if not isinstance(prop, list):
    prop = prop.split('.')

  if prop[0] in obj:
    if len(prop) == 1:
      return obj[prop[0]]
    else:  
      return get_prop(obj[prop[0]], prop[1:])
  return None

def download_metrics(org_id, project_id, cluster_id, host_id, retention, file_suffix):
  url = METRICS_URL.format(BASE_URL, project_id, host_id, retention)
  resp = requests.get(url, headers=HEADERS, verify=NO_VERIFY)
  if not resp.ok:
    exit_on_bad_response(resp)
  metrics_json = resp.json()
  
  # write metrics output
  file_path = "{}/{}/{}{}.json".format(org_id, project_id, host_id, file_suffix)
  with open(file_path, 'w') as fp:
    json.dump(metrics_json, fp)

def makedirs(path):
  if not os.path.exists(path):
    os.makedirs(path)

def exit_on_bad_response(resp):
  sys.exit(f"Error! Got {resp.status_code} when requesting: {resp.url}")

def in_filter_startswith(name, list):
  for elm in list:
    if name.startswith(elm):
      return True
  return False

if __name__ == '__main__':
  description = "Downloads cluster info and metrics for an org in Ops Manager"
  parser = ArgumentParser(description=description)
  parser.add_argument('auth_cookie', help="Authentication cookie for Ops Manager", metavar='AUTHCOOKIE')
  parser.add_argument('-u', '--url', help="Base URL for Ops Manager (leave blank if Atlas)", default=DEFAULT_BASE_URL, metavar='BASEURL')
  parser.add_argument('-o', '--org', help="Get data for specific org ID (can specify multiple) (required if Atlas)", metavar='ORGID', action='append')
  parser.add_argument('-n', '--noverify', help="Do not verify SSL certificate", action='store_false')
  parser.add_argument('-p', '--project', help="Filter by project ID", action='append', default=[], metavar='PROJECTID')
  parser.add_argument('-c', '--cluster', help="Filter by cluster name starts with <CLUSTERNAME>", action='append', default=[], metavar='CLUSTERNAME')

  args = parser.parse_args()
  global BASE_URL
  BASE_URL = args.url
  
  global HEADERS
  cookie_name = 'mmsa-prod='
  if BASE_URL != DEFAULT_BASE_URL:
    cookie_name = 'mmsa-hosted='
  HEADERS = {
    'Cookie': cookie_name + args.auth_cookie
  }

  global NO_VERIFY
  NO_VERIFY = args.noverify
  
  global PROJECT_FILTER
  PROJECT_FILTER = args.project
  global CLUSTER_FILTER
  CLUSTER_FILTER = args.cluster
  
  if not args.org and BASE_URL == DEFAULT_BASE_URL:
    sys.exit(f"You have to specify at least one org when querying Atlas! Exiting...")

  main(args.org)