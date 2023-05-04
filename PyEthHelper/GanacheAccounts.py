#!/usr/bin/env python3
# -*- coding:utf-8 -*-
###
# Copyright (c) 2023 Haofan Zheng
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.
###


import argparse
import json
import os
import web3

from typing import Dict
from web3 import Web3


# check web3 version
if list(map(int, web3.__version__.split('.'))) < [ 6, 2, 0 ]:
	raise RuntimeError(
		'web3 version {} is not supported; '
		'please upgrade to version 6.2.0 or above.'.format(web3.__version__)
	)


def ChecksumGanacheKeysFile(dest: os.PathLike, src: os.PathLike):
	with open(src, 'r') as f:
		keysJson: Dict[str, Dict[str, str]] = json.load(f)

	addrs = keysJson['addresses']
	addrs = {
		Web3.to_checksum_address(k): Web3.to_checksum_address(v)
			for k, v in addrs.items()
	}
	keysJson['addresses'] = addrs

	privKeys = keysJson['private_keys']
	privKeys = {
		Web3.to_checksum_address(k): v for k, v in privKeys.items()
	}
	keysJson['private_keys'] = privKeys

	with open(dest, 'w') as f:
		json.dump(keysJson, f, indent='\t')


def main():
	argParser = argparse.ArgumentParser(
		description='Helper scripts for Ganache accounts'
	)
	argParserOps = argParser.add_subparsers(
		dest='operation', required=True,
		help='Operation to be performed',
	)
	argParserOpChksum = argParserOps.add_parser(
		'checksum',
		help='Convert Ganache keys file to checksum format'
	)
	argParserOpChksum.add_argument(
		'--output', '-o', type=str, required=True,
		help='Output file path'
	)
	argParserOpChksum.add_argument(
		'--input', '-i', type=str, required=True,
		help='Input file path'
	)
	args = argParser.parse_args()

	if args.operation == 'checksum':
		ChecksumGanacheKeysFile(args.output, args.input)
	else:
		raise RuntimeError('Unknown operation: {}'.format(args.operation))


if __name__ == '__main__':
	main()
