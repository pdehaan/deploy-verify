import os
import argparse
from deploy_verify.bugzilla_rest_client import BugzillaRESTClient
from deploy_verify.release_notes import ReleaseNotes
from deploy_verify.ec2_handler import EC2Handler 
from deploy_verify.stack_checker import StackChecker 
from output_helper import OutputHelper


URL_BUGZILLA_PROD = 'https://bugzilla.mozilla.org'
URL_BUGZILLA_DEV = 'https://bugzilla-dev.allizom.org'


def ticket(args=None):

    parser = argparse.ArgumentParser(
        description='Scripts for creating / updating deployment tickets in \
        Bugzilla',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # parser for ticket - any option 
    parser.add_argument(
        '-u', '--bugzilla-username',
        required=True)

    parser.add_argument(
        '-p', '--bugzilla-password',
        required=True)

    parser.add_argument(
        '-B', '--bugzilla-mozilla',
        help='Set this switch to post directly to bugzilla.mozilla.org \
            (without switch posts to: bugzilla-dev.allizom.org)',
        action='store_true',
        default=False,
        required=False)

    subparsers = parser.add_subparsers(help='Ticket action')

    # parser for ticket - {create} option
    parser_create = subparsers.add_parser('NEW', 
        help='Create a NEW deployment ticket.')

    parser_create.add_argument(
        '-o', '--repo-owner',
        help='Example: mozilla-services',
        default='mozilla-services',
        required=False)

    parser_create.add_argument(
        '-r', '--repo',
        help='Example: loop-server',
        required=True)

    parser_create.add_argument(
        '-e', '--environment',
        help='Enter: STAGE, PRODUCTION',
        default='STAGE',
        required=False)

    parser_create.add_argument(
        '-m', '--cc-mail',
        help='Example: xyz-services-dev@mozilla.com \
            NOTE: must be a registered username!',
        default='',
        required=False)

    # parser for ticket - {upate} option
    parser_update = subparsers.add_parser('UPDATE', 
        help='UPDATE an existing deployment ticket')
    parser_update.add_argument(
        '-i', '--bug-id',
        help='Example: 1234567',
        required=True)

    parser_update.add_argument(
        '-c', '--comment',
        help='Enter: <your bug comment>',
        required=True)

    args = vars(parser.parse_args())

    bugzilla_username = args['bugzilla_username']
    bugzilla_password = args['bugzilla_password']

    if args['bugzilla_mozilla']:
        #TODO:
        exit('REMOVE BEFORE MERGING!!!')
        url_bugzilla = URL_BUGZILLA_PROD
    else:
        url_bugzilla = URL_BUGZILLA_DEV

    ticket = BugzillaRESTClient(
        url_bugzilla, bugzilla_username, bugzilla_password)

    if all (key in args for key in ['bug_id','comment']):
        bug_id = args['bug_id']
        comment = args['comment']

        ticket.bug_update(bug_id, comment) 

    if all (key in args for key in ['repo_owner', 'repo', 'environment']):
        repo_owner = args['repo_owner']
        repo = args['repo']
        environment = args['environment']
        if args['cc_mail']:
            cc_mail = args['cc_mail']
        else:
            cc_mail = ''
        status = 'NEW'

        output = OutputHelper()
        output.log('Create deployment ticket', True, True)
        notes = ReleaseNotes(repo_owner, repo, environment)
        description = notes.get_release_notes()
        release_num = notes.last_tag
        output.log('Release Notes', True)
        output.log(description)

        ticket.bug_create(release_num, repo, environment, status, description, cc_mail)

def stack_check(args=None):
    """Verify newly deployed stack and update bug with verification results

    TODO:
        Ops Jenkins must call stack-check with the id of the deployment bug.

        option #1: 
            (implemented here) We grab the latest instance(s) and 
            assume that's the one we want to test
        option #2:  
            Ops Jenkins hands us off the DNS of the newly deployed stack 
            as an input param

        From Ops Jenkins:
        /var/log/initial_puppet_apply.log
        Sun Feb 01 10:57:55 +0000 2015 Puppet (notice): Finished catalog run in 422.65 seconds
        Jenkins will provide the host DNS as input param
        we need a static URL to reference stage.loop.mozaws.net
    """

    parser = argparse.ArgumentParser(
        description='Sanity check for basic stack deployment verification',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('-a','--application',
                help='Enter: loop-server, loop-client',
                default='loop-server',
                required=True)
    parser.add_argument('-r','--region',
                help='Enter: eu-west-1, us-east-1',
                default='eu-west-1',
                required=True)
    # Add as optional filter, without which we simply choose latest
    # We may also want to filter out a previous version
    parser.add_argument('-t','--tag-num',
                help='Enter: 0.17.2',
                required=False)
    parser.add_argument(
                '-e', '--environment',
                help='Enter: STAGE, PRODUCTION',
                default='STAGE',
                required=False)
    parser.add_argument('-i','--deployment-ticket-id',
                help='Enter: 1234567',
                required=True)
    parser.add_argument('-u', '--bugzilla-username',
                required=True)
    parser.add_argument('-p', '--bugzilla-password',
                required=True)
    parser.add_argument('-B', '--bugzilla-mozilla',
                help='Set this switch to post directly to bugzilla.mozilla.org \
                    (without switch posts to: bugzilla-dev.allizom.org)',
                action='store_true',
                default=False,
                required=False)

    args = vars(parser.parse_args())

    application = args['application']
    region = args['region']
    tag_num = args['tag_num']
    environment = args['environment']
    bug_id = args['deployment_ticket_id']
    bugzilla_username = args['bugzilla_username']
    bugzilla_password = args['bugzilla_password']

    if args['bugzilla_mozilla']:
        #TODO:
        exit('REMOVE BEFORE MERGING!!!')
        url_bugzilla = URL_BUGZILLA_PROD
    else:
        url_bugzilla = URL_BUGZILLA_DEV

    ticket = BugzillaRESTClient(
        url_bugzilla, bugzilla_username, bugzilla_password)

    bastion_username = os.environ["BASTION_USERNAME"] 
    bastion_host = os.environ["BASTION_HOST"] 
    bastion_port = os.environ["BASTION_PORT"] 
    bastion_host_uri = '{}@{}:{}'.format( 
        bastion_username, bastion_host, bastion_port)

    ec2 = EC2Handler()
    filters = {
        'tag:Type': application.replace('-', '_') 
    }
    instances = ec2.instances_newest(region, filters)

    for instance in instances:
        host_string = instance.public_dns_name

        check = StackChecker(
            bastion_host_uri, application, tag_num, environment, host_string)
        result = check.main()

        comment = host_string
        ticket.bug_update(bug_id, result)

def loadtest(args=None):
    parser = argparse.ArgumentParser(
        description='Run loadtest to verify scalability (STAGE only)',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        '-t', '--test',
        help='Example: this is placeholder text',
        default='hello loadtest',
        required=False)

    args = vars(parser.parse_args())

def e2e_test(args=None):
    parser = argparse.ArgumentParser(
        description='Run e2e test for final STAGE verification',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        '-t', '--test',
        help='Example: this is placeholder text',
        default='hello e2e',
        required=False)

    args = vars(parser.parse_args())
