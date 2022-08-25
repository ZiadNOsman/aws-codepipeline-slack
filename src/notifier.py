# -*- coding: utf-8 -*-

from __future__ import print_function

import json
import time

import boto3
# from test_events import TEST_EVENTS, TEST_ERROR_EVENTS
from build_info import BuildInfo, CodeBuildInfo
from message_builder import MessageBuilder
from slack_helper import find_message_for_build, post_build_msg, send_msg

# import re
# import sys

client = boto3.client('codepipeline')

def findRevisionInfo(info):
    r = client.get_pipeline_execution(
        pipelineName=info.pipeline,
        pipelineExecutionId=info.executionId
    )['pipelineExecution']

    revs = r.get('artifactRevisions',[])
    if len(revs) > 0:
        return revs[0]
    return None


def pipelineFromBuild(codeBuildInfo):
    r = client.get_pipeline_state(name=codeBuildInfo.pipeline)

    for s in r['stageStates']:
        for a in s['actionStates']:
            executionId = a.get('latestExecution', {}).get('externalExecutionId')
            if executionId and codeBuildInfo.buildId.endswith(executionId):
                pe = s['latestExecution']['pipelineExecutionId']
                return (s['stageName'], pe, a)
    return (None, None, None)


def processCodePipeline(event):
    buildInfo = BuildInfo.fromEvent(event)
    existing_msg = find_message_for_build(buildInfo)
    builder = MessageBuilder(buildInfo, existing_msg)
    builder.updatePipelineEvent(event)

    if builder.needsRevisionInfo():
        revision = findRevisionInfo(buildInfo)
        builder.attachRevisionInfo(revision)

    post_build_msg(builder)

def processCodeBuild(event):
    cbi = CodeBuildInfo.fromEvent(event)
    (stage, pid, actionStates) = pipelineFromBuild(cbi)

    if not pid:
        return

    buildInfo = BuildInfo(pid, cbi.pipeline)

    existing_msg = find_message_for_build(buildInfo)
    builder = MessageBuilder(buildInfo, existing_msg)

    if 'phases' in event['detail']['additional-information']:
        phases = event['detail']['additional-information']['phases']
        builder.updateBuildStageInfo(stage, phases, actionStates)

    logs = event['detail'].get('additional-information', {}).get('logs')
    if logs:
        builder.attachLogs(event['detail']['additional-information']['logs'])

    post_build_msg(builder)


def process(event):
    if 'queryStringParameters' in event:
        if "git-tag" in event['queryStringParameters']:
            if event['queryStringParameters']['git-tag'] == "":
                send_msg(ch=None, attachments=None, git_tag="not specified")
            else:
                send_msg(ch=None, attachments=None, git_tag=event['queryStringParameters']['git-tag'])
    if event['source'] == "aws.codepipeline":
        processCodePipeline(event)
    if event['source'] == "aws.codebuild":
        processCodeBuild(event)

def run(event, context):
    #print(json.dumps(event, indent=2, default=str))
    m = process(event)

if __name__ == "__main__":
    with open ('test-event.json') as f:
        events = json.load(f)
        for e in events:
            run(e, {})
            time.sleep(1)
