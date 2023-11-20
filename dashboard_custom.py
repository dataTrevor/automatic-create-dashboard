########################
#### Env: python3.9
#### Function1: Use the default template(we defined it as most customers need), help customer to create a new dashboard, and add a instance or many instances of a cluster
###  into each widget of the created dashboard. --init option
#### Function2: Customer created a dashboard from aws cloudwatch console or Function1, and selected one RDS cluster as template, after that, customer can add a instance or many instances
###  into each widget of the dashboard.
#### Function3: Download the cloudWatch dashboard to a local json file as template. --unload option
#### prerequisite: you need configure ak/sk in AWS CLI first, and make sure you have privileges to call aws SDK api.
#### created by king_516@126.com , 2023-10-16
########################
import boto3
import json
import re
import argparse

def args_parse():
    parser = argparse.ArgumentParser(description='Create CloudWatch Dashboard automatically')
    parser.add_argument('--template', '-t', help='dashboard template file name, mandatory', default='Aurora_monitor_DashboardBody.json', required=False)
    parser.add_argument('--dashName', '-n', help='dashboard template name in aws console, optional', required=True)
    parser.add_argument('--business', '-b', help='business name which to be displayed as cloudwatch dashboard name, optional', required=False)
    parser.add_argument('--clusterId', '-c', help='Aurora DB cluster identifier in AWS', required=False)
    parser.add_argument('--tag', '-tag', help='Aurora DB cluster tag in console tags, such as RG:UAT or "RG:UAT", resourcegroup:UAT', required=False)
    parser.add_argument('--region', '-r', help='The Region of Aurora DB cluster identifier, mandatory', default='ap-northeast-1', required=True)
    parser.add_argument('--service', '-s', help='The service you want to monitor , default RDS, optional', default='RDS', required=False)
    parser.add_argument('--unload', '-u', help='Unload the dashboard template from cloudWatch , optional', required=False)
    parser.add_argument('--init', '-i', help='Create a new dashboard in cloudWatch as local json dashboard body , optional', default=False, action='store_true')

    args = parser.parse_args()
    return args

def getClient(srvName, region_name):
    client = boto3.client(srvName, region_name)
    return client

# get cloudWatch dashboard
def getDashboard(client, dashName):
    response = client.get_dashboard(
        DashboardName = dashName
    )
    return response
# update dashboard as local dashboard body
def updateDashboard(client, dashName, dashboardBody):
    try:
        client.put_dashboard(
            DashboardName = dashName,
            DashboardBody = dashboardBody
        )
    except Exception as e:
        print(e)
# transfer Json object to String, as required by AWS SDK
def createDashboardBody(widgets):
    dashboardBodyDict = {'widgets': widgets}
    dashboardBody = json.dumps(dashboardBodyDict)
    return dashboardBody

# match metric(like CPUUtilization) to remove old metricDict from Widgets
def matchMetricWidgetInWidgets(curWidgets, srvSKU, metricName):
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
def addMetricIntoWidgetDict(widgetDict, srvSKU, metricName, clusterInstanceList, region, lableDetailList, isInit: bool = False):
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
    print("Instance amount of Cluster is: %d, %d instances's metric %s be added this time because existed! " % (len(clusterInstanceList), (len(clusterInstanceList) - repeatNum), metricName))
    return widgetDict 

# check whether the instance's metric has been added into monitor, not to repeat adding.
def findDuplicateMetric(lableDetailList, metricName, clusterId, instanceId, role, region):
    isDuplicate = False
    # labelDetail is like: ap-northeast-1-CPUUtilization-aurora-2-standard-WRITER
    labelDetail =  region + '-' + metricName + '-' + instanceId + '-' +role
    if labelDetail in lableDetailList:
        isDuplicate = True
        return isDuplicate
    return isDuplicate

# build a label list of an online widget, provide a label list to avoid duplicate metric of one instance
def buildLabelListFromEachWidget(widgetDict, metricName):
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
def buildAllLabelList(onlineWidgets, metricName):
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
def buildAllMetricList(onlineWidgets, srvSKU):
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
def updateWidgetJson(curWidgets, srvSKU, metricName, clusterInstanceList, region, isInit: bool = False):
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
def tagMatched(tagInput: str, tagPair):
    matched = False
    tags = tagInput.split(":",1)
    key = tags[0]
    value = tags[1]
    if key == tagPair.get("Key") and value == tagPair.get("Value"):
        matched = True
    return matched

# dbInstances is the Json in DBClusterMembers, return a list[{"DBInstanceIdentifier":"aurora-test-instance-1","DBClusterIdentifier": "aurora-test","role":"WRITER"}, ]
def convertClusterInstancesToInstanceList(dbInstances, clusterId):
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
def getClusterInstances(client, clusterId, region, tag):
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
        print(dbclusters)
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

'''metric name is from customer needs, such as [CPUUtilization, SelectLatency, InsertLatency,
   UpdateLatency, DeleteLatency, FreeableMemory, WriteIOPS, ReadIOPS]
 '''
# metricName = 'CPUUtilization'
# get Widgets from aws cloud watch
def getConsoleWidgets(client, dashName, region_name):
    # step1. get dashboard template
    response = getDashboard(client, dashName)
    dashboardBody = response['DashboardBody']
    bodyJson =  json.loads(dashboardBody)
    #print(response['DashboardBody'])
    return bodyJson['widgets']

def listAllDashboards(client, dashName, region_name):
    response = client.list_dashboards(
        DashboardNamePrefix=dashName
    )
    #print(type(response['DashboardEntries']))
    return response['DashboardEntries']

# open the local json config
def getTemplateWidgets():
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
def initDashboardWidgets(templateWidgets, srvSKU, clusterInstanceList, region):
    metriList = buildAllMetricList(templateWidgets, srvSKU)
    for metricName in metriList:
        initWidgets = updateWidgetJson(templateWidgets, srvSKU, metricName, clusterInstanceList, region, True)
    return initWidgets

srvSKU = 'AWS/RDS'
# parameters check
args = args_parse()
clusterId = args.clusterId
tag = args.tag
region = args.region
unloadFile =  args.unload
isInit = args.init
dashName = args.dashName
print("isInit = ", args.init)
if isInit:
    # clusterID is necessary in init
    if clusterId is None:
        print("Parameters Error: clusterId is needed in init mode!")
        exit()
else:
    if clusterId is None and tag is None:
        print("Parameters Error: Ether clusterId or tag is necesary!")
        exit()
if tag != None:
    tags = tag.split(":",1)
    if len(tags) < 2:
        print("Parameters Error: tag %s is invalid!" % tag)
        exit()

if __name__ == '__main__':
    # get template of dashboard'
    client = getClient('rds', region)
    # step2. get clusterInstanceList, [{'Role': 'WRITER', 'DBClusterIdentifier': 'aurora-1', 'DBInstanceIdentifier': 'aurora-1-primary'},{'Role': 'READER', 'DBClusterIdentifier': 'aurora-1', 'DBInstanceIdentifier': 'aurora-1-replica1'}]
    clusterInstanceList = []
    try:
        clusterInstanceList = getClusterInstances(client, clusterId, region, tag)
    except client.exceptions.DBClusterNotFoundFault as e:
        print("Your RDS cluster not found: %s" % clusterId)
        exit()
    print("Your RDS cluster size: %d" % len(clusterInstanceList))
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
    #res = getDashboard(client, dashName)
    #print("new dashboardBody: ", res['DashboardBody'])
