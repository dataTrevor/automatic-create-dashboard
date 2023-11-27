# Introduction of automatic-create-dashboard
Users can create a custom dashboard including multi RDS/Aurora clusters in AWS CloudWatch. With the custom dashboard, user can custom the RDS/Aurora cluster's metrics in one dashboard, and add new clusters into the dashboard automatically.

# Prerequisite
1. Install the Python 3
2. Configure the AWS credentials
The python script connects AWS with Boto3. Before use this tool, you must have both AWS credentials and an AWS Region set in order to make requests. If you have the AWS CLI, then you can use its interactive configure command to set up your credentials and default region: 
aws configure
Follow the prompts and it will generate configuration files in the correct locations for you. For details, refer to https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html#cli-configure-files-methods

# How to use
1. init a new dashboard with default template
```
python dashboard_custom.py --init --dashName <new dashboard name you want> --clusterId <a aurora cluster id> --region <region where your Aurora is>
```
Info: you must specify a cluster when you init a new dashboard.
2. add a cluster into old dashboard
```
python dashboard_custom.py --update --dashName <old dashboard name you want> --clusterId <a new aurora cluster id> --region ap-northeast-1
```
3. add all clusters into old dashboard by scanning the tags in your RDS clusters
```
python dashboard_custom.py --update --dashName <old dashboard name you want> --tag "ResourceGroup:pre" --region ap-northeast-1 
```
Info: the tags you input in --tag option have to be tagged on Aurora clusters before.
4. add a tag for some clusters
```
python dashboard_custom.py --addtag --clusterId <clusterid1,clusterid2,clusterid3> --tag "ResourceGroup:pre" --region ap-northeast-1 
```
Info: Remove tag from Aurora clusters by replacing action option to --rmtag.