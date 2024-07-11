#!/usr/bin/env python3
# -*- coding:utf-8 -*-
###
# Copyright (c) 2024 Haofan Zheng
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.
###


import time
from typing import List

import web3

from web3.contract import Contract
from web3.contract.contract import ContractEvent


class ContractEventHelper:

	@classmethod
	def GetBlockPeriod(
		cls,
		w3: web3.Web3,
		probeBlkNum: int,
	) -> int:
		probeBlk = w3.eth.get_block(probeBlkNum)
		prevBlk = w3.eth.get_block(probeBlkNum - 1)
		return probeBlk.timestamp - prevBlk.timestamp

	@classmethod
	def WaitForEvent(
		cls,
		w3: web3.Web3,
		event: ContractEvent,
		fromBlock: int,
		timeoutByBlkNum: int = -1,
	) -> List[dict]:
		blkPeriodHalf = cls.GetBlockPeriod(w3, fromBlock) / 2

		queriedBlkNum = fromBlock - 1
		currBlkNum = w3.eth.block_number
		while True:
			if queriedBlkNum >= currBlkNum:
				# wait for new blocks
				time.sleep(blkPeriodHalf)
				currBlkNum = w3.eth.block_number
				continue

			queriedBlkNum += 1
			logs = event.get_logs(fromBlock=queriedBlkNum, toBlock=queriedBlkNum)
			if len(logs) > 0:
				return logs

			if (
				(timeoutByBlkNum > 0) and
				(queriedBlkNum >= (fromBlock + timeoutByBlkNum))
			):
				return []

	@classmethod
	def WaitForContractEvent(
		cls,
		w3: web3.Web3,
		contract: Contract,
		eventName: str,
		fromBlock: int,
		timeoutByBlkNum: int = -1,
	) -> List[dict]:
		return cls.WaitForEvent(
			w3=w3,
			event=contract.events[eventName](),
			fromBlock=fromBlock,
			timeoutByBlkNum=timeoutByBlkNum,
		)

