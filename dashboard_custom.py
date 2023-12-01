########################
#### Env: python3.9
#### Function1: Use the default template(we defined it as most customers need), help customer to create a new CloudWatch dashboard, and add a instance or many instances of a cluster
###  into each widget of the created dashboard. --init option
#### Function2: Customer created a dashboard as template from AWS CloudWatch console or Function1, after that, customer can add a instance or many instances
###  into each widget of the dashboard.
#### Function3: Download the cloudWatch dashboard to a local json file as template. --download option
#### prerequisite: you need configure ak/sk in AWS CLI first, and make sure you have privileges to call aws SDK api.
#### created by king_516@126.com , 2023-10-16
########################
import boto3
import json
import re
import argparse
from typing import List, Dict

def args_parse():
    parser = argparse.ArgumentParser(description='Create CloudWatch Dashboard automatically')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--init', '-i', action='store_true', help='Create a new dashboard in cloudWatch as local json dashboard body , optional')
    group.add_argument('--update', '-u', action='store_true', help='update dashboard in cloudWatch to add more clusters , optional')
    group.add_argument('--addtag', '-add', action='store_true', help='Add a tag to Aurora clusters , optional')
    group.add_argument('--rmtag', '-rm', action='store_true', help='Remove a tag from Aurora clusters , optional')
    parser.add_argument('--template', '-t', help='dashboard template file name, mandatory', default='Aurora_monitor_DashboardBody.json', required=False)
    parser.add_argument('--dashName', '-n', help='dashboard template name in aws console, optional', required=False)
    parser.add_argument('--business', '-b', help='business name which to be displayed as cloudwatch dashboard name, optional', required=False)
    parser.add_argument('--clusterId', '-c', help='Aurora DB cluster identifier in AWS, if tagging or removing tag, can be input like cluster1,cluster2,cluster3', required=False)
    parser.add_argument('--tag', '-tag', help='Aurora DB cluster tag in console tags, such as RG:UAT or "RG:UAT", resourcegroup:UAT', required=False)
    parser.add_argument('--region', '-r', help='The Region of Aurora DB cluster identifier, mandatory', default='ap-northeast-1', required=True)
    parser.add_argument('--service', '-s', help='The service you want to monitor , default RDS, optional', default='RDS', required=False)
    parser.add_argument('--download', '-d', help='Download the dashboard template from cloudWatch , optional', required=False)
    args = parser.parse_args()
    return args

def getClient(srvName: str, region_name: str):
    client = boto3.client(srvName, region_name)
    return client

# get cloudWatch dashboard
def getDashboard(client, dashName: str):
    response = client.get_dashboard(
        DashboardName = dashName
    )
    return response
# update dashboard as local dashboard body
def updateDashboard(client, dashName: str, dashboardBody: str):
    try:
        client.put_dashboard(
            DashboardName = dashName,
            DashboardBody = dashboardBody
        )
    except Exception as e:
        print(e)
# transfer Json object to String, as required by AWS SDK
def createDashboardBody(widgets) -> str:
    dashboardBodyDict = {'widgets': widgets}
    dashboardBody = json.dumps(dashboardBodyDict)
    return dashboardBody

# match metric(like CPUUtilization) to remove old metricDict from Widgets
def matchMetricWidgetInWidgets(curWidgets: List, srvSKU: str, metricName: str):
    matchId = None
    for i in range(len(curWidgets)):
        properties = curWidgets[i].get('properties')
        metrics = properties.get('metrics')
        for j in range(len(metrics)):
            metricElementList = metrics[j]
            # judge whether srvSKU(metricElementList[0]) is like 'AWS/RDS'
            res = re.search('^[a-zA-Z]', metricElementList[0])
            if res and metricElementList[0] == srvSKU and metricElementList[1] == metricName :
                matchId = i
                return matchId
    return matchId

# add metrics of instances into WidgetDict
def addMetricIntoWidgetDict(widgetDict: Dict, srvSKU: str, metricName: str, clusterInstanceList, region: str, lableDetailList, isInit: bool = False) -> Dict:
    properties = widgetDict.get('properties')
    metricList = properties.get('metrics')
    # delete template's metric from widgetDict when init a new dashboard
    if isInit:
        metricList = []
    #labelRegionMap =  {"region": region, "period": 60}
    widgetPeriod = properties.get("period")
    repeatNum = 0
    for i in range(len(clusterInstanceList)):
        labelRegionMap = {}
        labelRegionMap =  {"region": region, "period": widgetPeriod}
        metricElement = []
        instanceMap = clusterInstanceList[i]
        clusterId =  instanceMap['DBClusterIdentifier']
        instanceId = instanceMap['DBInstanceIdentifier']
        role = instanceMap['Role']
        #not repeat to add 
        if findDuplicateMetric(lableDetailList, metricName, clusterId, instanceId, role, region):
            repeatNum = repeatNum + 1
            continue
        metricElement.append(srvSKU)
        metricElement.append(metricName)
        metricElement.append("Role")
        # role in clusterInstanceList to be added monitor
        metricElement.append(role)
        # DBClusterIdentifier in clusterInstanceList to be added monitor
        metricElement.append("DBClusterIdentifier")
        metricElement.append(clusterId)
        # { "region": "ap-northeast-1", "label": "SelectLatency - cluster - writer" } 
        labelRegionMap['label'] = instanceId + '-' + role
        metricElement.append(labelRegionMap)
        metricList.append(metricElement)
    properties['metrics'] = metricList
    widgetDict['properties'] = properties
    print("Instance amount of Cluster is: %d, %d instances's metric %s be not added because duplicate! " % (len(clusterInstanceList), repeatNum, metricName) )
    return widgetDict 

# check whether the instance's metric has been added into monitor, not to repeat adding.
def findDuplicateMetric(lableDetailList: List, metricName: str, clusterId: str, instanceId: str, role: str, region: str) -> bool:
    isDuplicate = False
    # labelDetail is like: ap-northeast-1-CPUUtilization-aurora-2-standard-WRITER
    labelDetail =  region + '-' + metricName + '-' + instanceId + '-' +role
    if labelDetail in lableDetailList:
        isDuplicate = True
        return isDuplicate
    return isDuplicate

# build a label list of an online widget, provide a label list to avoid duplicate metric of one instance
def buildLabelListFromEachWidget(widgetDict: Dict, metricName: str) -> List:
    labelList = []
    properties = widgetDict.get('properties')
    metrics = properties.get('metrics')
    for j in range(len(metrics)):
        metricElementList = metrics[j]
        labelRegionMap = metricElementList[-1]
        #print(labelRegionMap)
        if 'label' not in labelRegionMap:
            labelKey = 'sample'
        else:
            labelKey = labelRegionMap.get('label')
        if 'region' not in labelRegionMap:
            labelRegionMap['region'] = properties.get('region')
        labelDetail = labelRegionMap.get('region') + '-' + metricName + '-' + labelKey
        if labelDetail not in labelList:
            labelList.append(labelDetail)
    return labelList

# build a label list of online widgets of dashboard
def buildAllLabelList(onlineWidgets: List, metricName: str) -> List:
    labelList = []
    for i in range(len(onlineWidgets)):
        properties = onlineWidgets[i].get('properties')
        metrics = properties.get('metrics')
        for j in range(len(metrics)):
            metricElementList = metrics[j]
            labelRegionMap = metricElementList[-1]
            #print(labelRegionMap)
            labelDetail = labelRegionMap.get('region') + '-' + metricName + '-' + labelRegionMap.get('label')
            if labelDetail not in labelList:
                labelList.append(labelDetail)
    return labelList

# build a widget(Metric) list of online widgets of dashboard template
def buildAllMetricList(onlineWidgets: List, srvSKU: str) -> List:
    metricList = []
    for i in range(len(onlineWidgets)):
        properties = onlineWidgets[i].get('properties')
        metrics = properties.get('metrics')
        for j in range(len(metrics)):
            metricElementList = metrics[j]
            # judge whether srvSKU(metricElementList[1]) is like 'CPUUtilization\SelectLatency'
            # print(metricElementList)
            res = re.search('^[a-zA-Z]', metricElementList[1])
            if res and metricElementList[0] == srvSKU:
                metricName = metricElementList[1]
                if metricName not in metricList:
                    metricList.append(metricName)
    return metricList

'''
    Parameters detail
    clusterInstanceList: it's a list to be monitored and added into Widgets, element is a dict {'Role': 'WRITER', 'DBClusterIdentifier': 'aurora-1'}
'''
def updateWidgetJson(curWidgets: List, srvSKU: str, metricName: str, clusterInstanceList, region: str, isInit: bool = False) -> List:
    machtchedWidgetId = matchMetricWidgetInWidgets(curWidgets, srvSKU, metricName)
    if machtchedWidgetId is None:
        print("Widget not found for this metric: %s", metricName)
    else:
        oldWidgetDict = curWidgets[machtchedWidgetId]
        del curWidgets[machtchedWidgetId]
        #print(curWidgets)
        #build all metric label list of oldWidgetDict
        labelDetailList = buildLabelListFromEachWidget(oldWidgetDict, metricName)
        newWidgetDict = addMetricIntoWidgetDict(oldWidgetDict, srvSKU, metricName, clusterInstanceList, region, labelDetailList, isInit)
        #whether del template metric from local json dashboard
        curWidgets.append(newWidgetDict)
    return curWidgets

# check tag(RG:pre) exists in RDS cluster TagPair like {'Key': 'RG', 'Value': 'pre'}
def tagMatched(tagInput: str, tagPair: Dict) -> bool:
    matched = False
    tags = tagInput.split(":",1)
    key = tags[0]
    value = tags[1]
    if key == tagPair.get("Key") and value == tagPair.get("Value"):
        matched = True
    return matched

# dbInstances is the Json in DBClusterMembers, return a list[{"DBInstanceIdentifier":"aurora-test-instance-1","DBClusterIdentifier": "aurora-test","role":"WRITER"}, ]
def convertClusterInstancesToInstanceList(dbInstances: List, clusterId: str) -> List:
    instanceList = []
    for i in range(len(dbInstances)):
            dbInstanceMap = {}
            dbInstanceMap["DBClusterIdentifier"] = clusterId
            dbInstanceMap["DBInstanceIdentifier"] = dbInstances[i].get("DBInstanceIdentifier")
            role = "READER"
            if dbInstances[i].get("IsClusterWriter"):
                role = "WRITER"
            dbInstanceMap["Role"] = role
            instanceList.append(dbInstanceMap)
    return instanceList

# get Aurora Instance list from AWS SDK by clusterID or tag, not for RDS instance!
def getClusterInstances(client, clusterId: str, region: str, tag: str) -> List:
    instanceList = []
    dbclusters = []
    dbInstances = []
    if clusterId != None:
        response = client.describe_db_clusters(
            DBClusterIdentifier = clusterId,
            Marker = 'string'
            )
        dbclusters = response['DBClusters']
        dbcluster = dbclusters[0]
        dbInstances = dbcluster.get("DBClusterMembers")
        instanceList = convertClusterInstancesToInstanceList(dbInstances, clusterId)
    elif tag != None:
        response = client.describe_db_clusters(
            Marker = 'string'
            )
        dbclusters = response['DBClusters']
        #print(dbclusters)
        for i in (range(len(dbclusters))):
            dbcluster = dbclusters[i]
            tagList = dbcluster.get("TagList")
            for j in range(len(tagList)):
                tagPair = tagList[j]
                if tagMatched(tag, tagPair):
                    dbInstances = dbcluster.get("DBClusterMembers")
                    instanceList = instanceList + convertClusterInstancesToInstanceList(dbInstances, dbcluster.get("DBClusterIdentifier"))
                    break
    return instanceList

def getClusterById(client, clusterId: str, region: str) -> Dict:
    dbcluster = {}
    if clusterId != None:
        response = client.describe_db_clusters(
            DBClusterIdentifier = clusterId,
            Marker = 'string'
            )
        dbclusters = response['DBClusters']
        dbcluster = dbclusters[0] if len(dbclusters) > 0 else {}
    return dbcluster

'''metric name is from customer needs, such as [CPUUtilization, SelectLatency, InsertLatency,
   UpdateLatency, DeleteLatency, FreeableMemory, WriteIOPS, ReadIOPS]
 '''
# metricName = 'CPUUtilization'
# get Widgets from aws cloud watch
def getConsoleWidgets(client, dashName: str, region_name: str) -> List:
    # step1. get dashboard template
    response = getDashboard(client, dashName)
    dashboardBody = response['DashboardBody']
    bodyJson =  json.loads(dashboardBody)
    #print(response['DashboardBody'])
    return bodyJson['widgets']

def listAllDashboards(client, dashName: str, region_name: str):
    response = client.list_dashboards(
        DashboardNamePrefix=dashName
    )
    #print(type(response['DashboardEntries']))
    return response['DashboardEntries']

# open the local json config
def getTemplateWidgets() -> List:
    f = open('Aurora_monitor_DashboardBody.json','r')
    widgetsList = json.load(f)
    f.close()
    #print(type(bodyJson))
    return widgetsList

# dump json object to local file
def writeTemplateWidgets(unloadFile, curWidgets):
    with open (unloadFile,'w') as f:
        json.dump(curWidgets, f)

# create a new widgets with a real clusterId and instances
def initDashboardWidgets(templateWidgets: List, srvSKU: str, clusterInstanceList: List, region: str) -> List:
    metriList = buildAllMetricList(templateWidgets, srvSKU)
    for metricName in metriList:
        initWidgets = updateWidgetJson(templateWidgets, srvSKU, metricName, clusterInstanceList, region, True)
    return initWidgets

def getClustersByIds(client, clusterIds: str, region: str) -> List:
    if clusterIds is None:
        print("Error: no clusterId be input, exit tagging/marking!")
        exit()
    clusterIdList = clusterIds.split(",")
    clusters = []
    for j in range(len(clusterIdList)):
        clusterId = clusterIdList[j]
        clusters.append(getClusterById(client, clusterId, region))
    return clusters

# tag all clusters user input
def taggingClustersWithTag(clusterIds: str, region: str, tag: str):
    tagPair = tag.split(":",1)
    key = tagPair[0]
    value = tagPair[1]
    client = getClient('rds', region)
    clusters = getClustersByIds(client, clusterIds, region)
    print("You have %d RDS clusters want to tag." % len(clusters))
    x = 0
    for i in range(len(clusters)):
        cluster = clusters[i]
        clusterArn = cluster.get("DBClusterArn")
        client.add_tags_to_resource(
            ResourceName = clusterArn,
            Tags=[
                {
                    'Key': key,
                    'Value': value
                },
            ]
        )
        x = x + 1
    print("%d RDS clusters have been tagged!" % x)

def removeTagForClusters(clusterIds: str, region: str, tag: str):
    tagPair = tag.split(":",1)
    key = tagPair[0]
    client = getClient('rds', region)
    clusters = getClustersByIds(client, clusterIds, region)
    print("You have %d RDS clusters to remove tag." % len(clusters))
    x = 0
    for i in range(len(clusters)):
        cluster = clusters[i]
        clusterArn = cluster.get("DBClusterArn")
        client.remove_tags_from_resource(
            ResourceName = clusterArn,
            TagKeys=[
                key,
            ],
        )
        x = x + 1
    print("%d RDS clusters'tag %s have been removed!" % (x, tag))

srvSKU = 'AWS/RDS'
# parameters check
args = args_parse()
clusterId = args.clusterId
tag = args.tag
region = args.region
unloadFile =  args.download
isInit = args.init
isUpdate = args.update
dashName = args.dashName
isTagging = args.addtag
removeTag = args.rmtag
print("isInit = ", args.init) if isInit else print("")
print("isUpdate = ", args.update) if isUpdate else print("")
print("isTagging = ", args.addtag) if isTagging else print("")
print("removeTag = ", args.rmtag) if removeTag else print("")


if isInit or isTagging or removeTag:
    # clusterID is necessary in init
    if clusterId is None:
        print("Parameters Error: clusterId is needed in init mode or marking tag mode!")
        exit()
    if (isTagging or removeTag ) and tag is None:
        print("Parameters Error: --tag is needed in mark tag mode!")
        exit()
else:
    # update mode , clusterId or tags is needed
    if clusterId is None and tag is None:
        print("Parameters Error: Ether clusterId or tag is necesary when update dashboard!")
        exit()
#dashboard Name can be None only when tagging clusters
if dashName is None and (isInit or isUpdate):
        print("Parameters Error: dashboard Name is necesary when init or update dashboard!")
        exit()

if tag != None:
    tags = tag.split(":",1)
    if len(tags) < 2:
        print("Parameters Error: tag %s is invalid!" % tag)
        exit()

if __name__ == '__main__':
    if isTagging:
        taggingClustersWithTag(clusterId, region, tag)
        exit()
    if removeTag:
        removeTagForClusters(clusterId, region, tag)
        exit()
    # get template of dashboard'
    client = getClient('rds', region)
    # step2. get clusterInstanceList, [{'Role': 'WRITER', 'DBClusterIdentifier': 'aurora-1', 'DBInstanceIdentifier': 'aurora-1-primary'},{'Role': 'READER', 'DBClusterIdentifier': 'aurora-1', 'DBInstanceIdentifier': 'aurora-1-replica1'}]
    clusterInstanceList = []
    try:
        clusterInstanceList = getClusterInstances(client, clusterId, region, tag)
    except client.exceptions.DBClusterNotFoundFault as e:
        print("Your RDS cluster not found: %s" % clusterId)
        exit()
    print("Your RDS cluster have %d instances." % len(clusterInstanceList))
    if len(clusterInstanceList) == 0:
        print("Your RDS cluster has no instances: %s" % clusterId)
        exit()
    print(clusterInstanceList)
    ################ step0. whether init a dashboard
    dashboardExist = False
    if isInit:
        client = getClient('cloudwatch', region)
        try:
            curAllDashboards = listAllDashboards(client, dashName, region)
            for i in range(len(curAllDashboards)):
                dashboard =  curAllDashboards[i]
                if dashName == dashboard.get("DashboardName"):
                    dashboardExist = True
                    print("the dashboard name %s has been found in cloudWatch" % dashName)
                    break
        except Exception as e:
            print("%s, list dashboards error: %s" % (dashName, e))
            exit()
        if not dashboardExist:
            # dashName has to be unique, if not ,exit
            templateWidgets = getTemplateWidgets()  # get from local json template
            # create a new dashboard named $dashName
            initWidgets = initDashboardWidgets(templateWidgets, srvSKU, clusterInstanceList, region)
            # client = getClient('cloudwatch', region)
            updateDashboard(client, dashName, createDashboardBody(initWidgets))
            print("the dashboard %s created in cloudWatch." % dashName)
        exit()
    if isUpdate:
        ############### if not init, add metrics for cluster
        # step1. download template from cloudWatch dashboard
        client = getClient('cloudwatch', region)
        try:
            curWidgets = getConsoleWidgets(client, dashName, region)
        except Exception as e:
            print(e)
            exit()
        # optional, dump dashboard to a local json file, and exit
        if unloadFile is not None:
            writeTemplateWidgets(unloadFile, curWidgets)
            print("Unload template compete: %s" % unloadFile)
            exit()
        # step3. add clusterInstanceList's metric one by one into curWidgets 
        metriList = buildAllMetricList(curWidgets, srvSKU)
        for metricName in metriList:
            curWidgets = updateWidgetJson(curWidgets, srvSKU, metricName, clusterInstanceList, region, isInit)
        # step4. update dashboard
        updateDashboard(client, dashName, createDashboardBody(curWidgets))
        #print("new dashboardBody: ", res['DashboardBody'])
