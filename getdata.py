from argparse import ArgumentParser
import csv
import json
import os
import requests
import sys

ORGS_URL = "{}/settings/orgs"
GROUPS_URL = "{}/orgs/{}/groups"
SERVER_URL = "{}/servers/list/{}?mapAutomationAgents=true&mapBackupAgents=true&mapMonitoringAgents=true&mapProcesses=true"
METRICS_URL = "{}/metrics/v1/groups/{}/hosts/{}/replicaset?retention={}"
CONFIG_DB_URL = "{}/metrics/v1/groups/{}/hosts/{}/databases/storage?retention={}&bucketed=false&databaseName=config"
RETENTION_METRICS = ["172800000", "604800000"] # 48 hours & 1 week
RETENTION_CONFIG_DB = "3600000" # 1 hour

def main():
  orgs = get_orgs()
  for org in orgs['orgs']:
    org_id = org['id']
    makedirs(org_id)
    projects = get_projects(org_id)
    for project in projects:
      project_id = project['id']
      makedirs(org_id + '/' + project_id)
      servers = get_servers(project_id)
      hosts = save_servers_and_get_hosts(servers)
      for host in hosts:
        cluster_id = host[0]
        host_id = host[1]
        for retention in RETENTION_METRICS:
          # download cluster metrics
          download_metrics(org_id, project_id, cluster_id, host_id, retention, "-metrics-" + retention)
        # download config db metrics
        download_metrics(org_id, project_id, cluster_id, host_id, RETENTION_CONFIG_DB, "-configdb")
    print(f"Processed org ${org_id}")
  print("Successfully downloaded all cluster data and metrics!")

def get_orgs():
  url = ORGS_URL.format(BASE_URL)
  resp = requests.get(url, headers=HEADERS)
  if resp.ok:
    return resp.json()
  else:
    exit_on_bad_response(resp)
    

def get_projects(org_id):
  url = GROUPS_URL.format(BASE_URL, org_id)
  resp = requests.get(url, headers=HEADERS)
  if resp.ok:
    return resp.json()
  else:
    exit_on_bad_response(resp)

def get_servers(project_id):
  url = SERVER_URL.format(BASE_URL, project_id)
  resp = requests.get(url, headers=HEADERS)
  if resp.ok:
    return resp.json()
  else:
    exit_on_bad_response(resp)

def save_servers_and_get_hosts(servers):
  hosts = []
  with open('clusters.csv', 'w', newline='') as csvfile:
    fieldnames = ['cluster_id', 'replica_set_id', 'name', 'host_id', 'replica_state', 'cpu', 'ram_mb', 'wt_cache_size_gb', 'version']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for server in servers:
      # if server['processes']:
      process = get_prop(server, 'processes')[0]
      state = get_prop(process, 'state')
      process_type = get_prop(process, 'processType')
      is_conf = get_prop(state, 'isConf')
      last_ping = get_prop(state, 'lastPing')
      if process_type == 'mongod' and is_conf == False and last_ping != 0:
      # and state['replicaState'] == 'PRIMARY':
        cluster_id = get_prop(state, 'clusterId')
        replica_set_id = get_prop(state, 'replicaSetId')
        name = get_prop(process, 'name')
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
  resp = requests.get(url, headers=HEADERS)
  if not resp.ok:
    exit_on_bad_response(resp)
  metrics_json = resp.json()
  
  # write metrics output
  file_path = "{}/{}/{}{}.json".format(org_id, project_id, cluster_id, file_suffix)
  with open(file_path, 'w') as fp:
    json.dump(metrics_json, fp)

def makedirs(path):
  if not os.path.exists(path):
    os.makedirs(path)

def exit_on_bad_response(resp):
  sys.exit(f"Error! Got {resp.status_code} when requesting: {resp.url}")

if __name__ == '__main__':
  description = "Downloads cluster info and metrics for an org in Ops Manager"
  parser = ArgumentParser(description=description)
  parser.add_argument('base_url', help="Base URL for Ops Manager", metavar='BASEURL')
  parser.add_argument('auth_cookie', help="Authentication cookie for Ops Manager", metavar='AUTHCOOKIE')

  args = parser.parse_args()
  global BASE_URL
  BASE_URL = args.base_url
  global HEADERS
  HEADERS = {
    'Cookie': 'mmsa-hosted=' + args.auth_cookie
  }

  main()