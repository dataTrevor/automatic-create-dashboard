import boto3
from datetime import datetime, timedelta
import sys
'''
Query the metrics for a Elasticache cluster from AWS CloudWatch;
It's average counter per minute, for all metrics;
metric_list = ['BytesUsedForCache','CurrItems','NetworkBytesIn','NetworkBytesOut','ReplicationBytes','GetTypeCmds','SetTypeCmds','EvalBasedCmds']
create time: 2025-02-26
usage:
must specify 4 parameters: region, cluster name, cluster_enabled: yes or no, metrics_duraion: week, day
Precondition:
1/install python3, boto3
2/configure your AWS credentials using the AWS CLI or environment variables.
'''
# get metrics of cluster-non-enabled
def get_elasticache_metrics(region, cluster_id, node_ids, metric_name, start_time, end_time, period):
    cloudwatch = boto3.client('cloudwatch', region_name=region)
    all_datapoints = []
    metrics = []
    for node_id in node_ids:
        response = cloudwatch.get_metric_statistics(
            Namespace='AWS/ElastiCache',
            MetricName=metric_name,
            Dimensions=[
                {'Name': 'CacheClusterId', 'Value': cluster_id},
                {'Name': 'CacheNodeId', 'Value': node_id}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=['Average']
        )
        metrics.append({
            'ClusterId': cluster_id,
            'NodeId': node_id,
            'Datapoints': response['Datapoints']
        })
        all_datapoints.extend(response['Datapoints'])

    return metrics, all_datapoints

# get metrics of replication group
def get_replication_group_metrics(replication_group_id, metric_name, start_time, end_time, period, region, nodes):
    # nodes = get_replication_group_nodes(replication_group_id, region)
    all_datapoints = []
    cloudwatch = boto3.client('cloudwatch', region_name=region)
    metrics = []
    i = 0
    for node in nodes:
        response = cloudwatch.get_metric_statistics(
            Namespace='AWS/ElastiCache',
            MetricName=metric_name,
            Dimensions=[
                {'Name': 'CacheClusterId', 'Value': node['CacheClusterId']},
                {'Name': 'CacheNodeId', 'Value': node['CacheNodeId']}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=['Average']
        )
        metrics.append({
            'ClusterId': replication_group_id,
            'NodeId': node['CacheClusterId'],
            'Datapoints': response['Datapoints']
        })
        #Datapoints have 2 keys: Timestamp and Average, {'Timestamp': datetime.datetime(2025, 2, 25, 10, 8, tzinfo=tzutc()), 'Average': 441294.0, 'Unit': 'Count'}
        all_datapoints.extend(response['Datapoints'])
        i = i + 1
        # number of data points are large lower than expected number of one day
        if all_datapoints and len(all_datapoints) < (1440 * i * 0.9):
            print(f"NodeId: {node['CacheClusterId']} , num of datapoints: {len(all_datapoints)}, there maybe exception about {metric_name} data in cloudWatch!")

    return metrics, all_datapoints

# get nodes of elasticache cluster-non-enabled
def get_ecache_node_ids(cluster_id, region):
    # Create an ElastiCache client
    elasticache = boto3.client('elasticache', region_name=region)

    try:
        # Call DescribeCacheClusters with ShowCacheNodeInfo=True to get detailed node information
        response = elasticache.describe_cache_clusters(
            CacheClusterId=cluster_id,
            ShowCacheNodeInfo=True
        )
        
        # Extract node IDs from the response
        if response['CacheClusters']:
            cluster = response['CacheClusters'][0]
            node_ids = [node['CacheNodeId'] for node in cluster['CacheNodes']]
            return node_ids
        else:
            return []
            
    except elasticache.exceptions.CacheClusterNotFoundFault:
        print(f"Cluster {cluster_id} not found")
        return []
    except Exception as e:
        print(f"Error retrieving node information: {str(e)}")
        return []

# get nodes of replication group
def get_replication_group_nodes(replication_group_id, region):
    # Create an ElastiCache client
    elasticache = boto3.client('elasticache', region_name=region)
    response = elasticache.describe_replication_groups(ReplicationGroupId=replication_group_id)
    nodes = []
    shard_cnt = 0
    if response['ReplicationGroups'][0]['NodeGroups']:
        shard_cnt = len(response['ReplicationGroups'][0]['NodeGroups'])
    for node_group in response['ReplicationGroups'][0]['NodeGroups']:
        for member in node_group['NodeGroupMembers']:
            nodes.append({
                'CacheClusterId': member['CacheClusterId'],
                'CacheNodeId': member['CacheNodeId']
            })
    return nodes, shard_cnt

# query all datapoints by the metric_name, and calculate the avg value
def get_avg_metric_with_name(metric_name, datapoints_cnt_total, region, cluster_id, cluster_enabled, period):
    #print(f"###################### Begin to query metrics {metric_name} for cluster {cluster_id}")
    metrics_by_nodes = []
    all_datapoints = []
    end_time = datetime.utcnow()
    nodes = []
    node_ids = []
    shard_cnt = 0
    # Max datapoints for GetMetricStatistics operation: the limit of 1440, so need execute multiple times.
    for i in range(datapoints_cnt_total // 1440) :
        start_time = end_time - timedelta(hours=24)
        if cluster_enabled == "yes":
            replication_group_id = cluster_id
            if i == 0 :
                nodes, shard_cnt = get_replication_group_nodes(replication_group_id, region)
            metrics_by_nodes, datapoints = get_replication_group_metrics(replication_group_id, metric_name, start_time, end_time, period, region, nodes)
            all_datapoints.extend(datapoints)
        else:
            if i == 0 :
                node_ids = get_ecache_node_ids(cluster_id, region)
            metrics_by_nodes, datapoints = get_elasticache_metrics(region, cluster_id, node_ids, metric_name, start_time, end_time, period)
            all_datapoints.extend(datapoints)
        end_time = start_time
    # Calculate the avg metric of all nodes from one cluster
    if all_datapoints:
        unit = ""
        for point in all_datapoints:
            unit = point['Unit']
            break         
        avg_metric = round(sum(point['Average'] for point in all_datapoints) / len(all_datapoints), 2)
        if metric_name in ['GetTypeCmds','SetTypeCmds','EvalBasedCmds']:
            # trans to metric per hour
            avg_metric =  transform_unit_to_per_hour(avg_metric, metric_name, unit)
            unit = "Count per hour"
        if unit == "Bytes":
            #trans to Mbytes
            avg_metric = transform_unit_to_Mbytes(avg_metric, metric_name, unit)
            unit = "Mbytes"
        return f"Average {metric_name} for cluster {cluster_id}: {avg_metric}, Unit: {unit}"
    else:
        avg_metric = 0
        return f"No metric data available for {metric_name} in cluster {cluster_id}"
    return avg_metric

def transform_unit_to_Mbytes(avg_metric, metric_name, unit):
    return round(avg_metric / 1024 / 1024, 2) # Mbytes

def transform_unit_to_per_hour(avg_metric, metric_name, unit):
    return avg_metric * 3600

# Example usage
if __name__ == "__main__":
    if len(sys.argv) < 4:
            print(f"Error: must specify 4 parameters: region, cluster name, cluster_enabled, metrics_duraion: week, day")
            sys.exit(1)
    region=sys.argv[1] # 'ap-northeast-1' or Replace with your region
    cluster_id=sys.argv[2] # 'test-2' or 'other name'
    cluster_enabled=sys.argv[3] # yes or no
    metrics_duraion=sys.argv[4] if len(sys.argv) >= 5 else 'day'
    
    if cluster_enabled is None or (cluster_enabled != 'yes' and cluster_enabled != 'no') :
        print(f"Elasticache is cluster-enabled or not, please specify in 3rd parameter: yes or no!")
        sys.exit(1)
    #metric_name = 'CurrItems'
    metric_list = ['BytesUsedForCache','CurrItems','NetworkBytesIn','NetworkBytesOut','ReplicationBytes','GetTypeCmds','SetTypeCmds','EvalBasedCmds']
    if metrics_duraion == 'week' :
        datapoints_cnt_total = 7 * 24 * 60 # 7 days * 24 hours * 60 minutes
    elif metrics_duraion == 'day':
        datapoints_cnt_total = 24 * 60
    
    period = 60  # a data point every 60 secs, 1 minute
    # query nodes of the cluster
    nodes = []
    shard_cnt = 1
    if cluster_enabled == "yes":
        nodes, shard_cnt = get_replication_group_nodes(cluster_id, region)
    else:
        nodes = get_ecache_node_ids(cluster_id, region)
    print(f"Total number of shards: {shard_cnt}, replicas per shard: {(len(nodes) // shard_cnt - 1)}, Node IDs for cluster {cluster_id}:")
    for node_id in nodes:
        print(f"- {node_id}")
    # loop metric_list to query average metric
    for metric_name in metric_list:
        # As usage of storage is increaing day by day, just query the latest day metirc
        if metric_name == "CurrItems" or metric_name == "BytesUsedForCache":
            datapoints_cnt_total = 24 * 60
        # query metrics by cluster and metric_name, and calcute the final input
        avg_metric = get_avg_metric_with_name(metric_name, datapoints_cnt_total, region, cluster_id, cluster_enabled, period)
        print(f"{avg_metric}")
