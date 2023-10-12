#!/usr/bin/env python3
# -*- coding:utf-8 -*-
###
# Copyright (c) 2023 Haofan Zheng
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.
###


import argparse
import logging

from web3 import Web3

from .EthContractHelper import (
	LoadContract,
	DeployContract,
	CallContractFunc,
	SetupSendingAccount,
	ConvertValToWei,
)


def main():
	argParser = argparse.ArgumentParser(
		description='Deploy contracts to Ethereum blockchain',
		prog='',
	)
	argParser.add_argument(
		'--config', '-c', type=str, default='project_conf.json', required=False,
		help='Path to the project configuration file'
	)
	argParser.add_argument(
		'--verbose', '-v', action='store_true',
		help='Verbose logging'
	)
	argParser.add_argument(
		'--http', type=str, default='http://localhost:7545', required=False,
		help='HTTP provider URL'
	)
	argParser.add_argument(
		'--key-json', type=str, default=None, required=False,
		help='Path to keys.json'
	)
	argParser.add_argument(
		'--account', type=int, default=0, required=False,
		help='Index of the account to use'
	)
	argParser.add_argument(
		'--release', type=str, default=None, required=False,
		help='Use prebuilt version from GitHub Release of given git version tag'
			'(if not set, local built version will be used)'
	)
	argParser.add_argument(
		'--contract', '-C', type=str, required=True,
		help='Contract name'
	)
	argParser.add_argument(
		'--gas', '-G', type=int, default=None, required=False,
		help='Gas limit'
	)
	argParser.add_argument(
		'--value', '-V', type=int, default=0, required=False,
		help='Value to be sent along with the transaction'
	)
	argParser.add_argument(
		'--value-unit', '-U', type=str, default='wei', required=False,
		choices=['ether', 'gwei', 'wei'],
		help='Unit of value (ether, gwei, wei)'
	)
	argParser.add_argument(
		'--no-confirm', action='store_true',
		help='Do not ask for confirmation'
	)

	# two operations: deploy and call
	argParserSubOp = argParser.add_subparsers(
		dest='operation', required=True,
		help='Operation to be performed',
	)

	argParserSubOpDeploy = argParserSubOp.add_parser(
		'deploy', help='Deploy contract'
	)
	argParserSubOpDeploy.add_argument(
		'--args', '--params', '-r', type=str, nargs='*', default=[], required=False,
		help='Constructor parameters'
	)

	argParserSubOpCall = argParserSubOp.add_parser(
		'call', help='Call functions of a deployed contract'
	)
	argParserSubOpCall.add_argument(
		'--address', '-d', type=str, default=None, required=True,
		help='Address of the contract to be called'
	)
	argParserSubOpCall.add_argument(
		'--function', '-f', type=str, required=True,
		help='The name of the function to be called'
	)
	argParserSubOpCall.add_argument(
		'--args', '--params', '-r', type=str, nargs='*', default=[], required=False,
		help='function parameters'
	)

	args = argParser.parse_args()

	address = None if args.operation != 'call' else args.address

	# logging configuration
	loggingFormat = '%(asctime)s %(levelname)s %(message)s'
	if args.verbose:
		logging.basicConfig(level=logging.DEBUG, format=loggingFormat)
	else:
		logging.basicConfig(level=logging.INFO, format=loggingFormat)
	logger = logging.getLogger(__name__ + main.__name__)

	# connect to Ethereum node
	w3 = Web3(Web3.HTTPProvider(args.http))
	if not w3.is_connected():
		raise RuntimeError(
			'Failed to connect to Ethereum node at %s' % args.http
		)

	valueToSend = ConvertValToWei(args.value, args.value_unit)
	privKey = SetupSendingAccount(w3, args.account, args.key_json)
	contract = LoadContract(
		w3=w3,
		projConf=args.config,
		contractName=args.contract,
		release=args.release,
		address=address
	)

	# deploy or call contract
	if args.operation == 'deploy':
		DeployContract(
			w3=w3,
			contract=contract,
			arguments=args.args,
			privKey=privKey,
			gas=args.gas,
			value=valueToSend,
			confirmPrompt=(not args.no_confirm)
		)
	elif args.operation == 'call':
		CallContractFunc(
			w3=w3,
			contract=contract,
			funcName=args.function,
			arguments=args.args,
			privKey=privKey,
			gas=args.gas,
			value=valueToSend,
			confirmPrompt=(not args.no_confirm)
		)


if __name__ == '__main__':
	main()

