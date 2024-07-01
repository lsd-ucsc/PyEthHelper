#!/usr/bin/env python3
# -*- coding:utf-8 -*-
###
# Copyright (c) 2024 Haofan Zheng
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.
###


import logging
import subprocess
import time

from typing import List, Union

import web3


class GethNodeGuard(object):

	def __init__(self, cmd: List[str], termTimeout: int = 10):
		super(GethNodeGuard, self).__init__()

		self.cmd = cmd
		self.termTimeout = termTimeout

		self.proc = None

		self.logger = logging.getLogger(f'{__name__}.{self.__class__.__name__}')

	def Start(self) -> None:
		cmdStr = ' '.join([str(x) for x in self.cmd])
		self.logger.info(f'Starting Geth node with command: {cmdStr}')
		self.proc = subprocess.Popen(
			[ str(x) for x in self.cmd ],
			stdin=subprocess.DEVNULL,
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
		)

	def Stop(self) -> None:
		if self.proc is not None:
			waitedTime = 0.0
			waitInterval = 1.0
			self.logger.info('Terminating the Geth node...')
			while self.proc.poll() is None:
				self.proc.terminate()
				startTime = time.time()
				try:
					self.proc.wait(timeout=waitInterval)
				except subprocess.TimeoutExpired:
					pass
				waitedTime += time.time() - startTime
				if waitedTime >= self.termTimeout:
					self.logger.info('Geth node did not terminate within the timeout, killing it...')
					self.proc.kill()

			self.proc = None
			self.logger.info('Geth node terminated.')

	def __enter__(self) -> 'GethNodeGuard':
		self.Start()
		return self

	def __exit__(self, exc_type, exc_value, traceback) -> None:
		self.Stop()


class GethDevNodeGuard(GethNodeGuard):

	DEV_CHAIN_ID = 1337
	DEV_BLOCK_PERIOD = 12
	DEV_GAS_LIMIT = 30 * 1000 * 1000

	DEFAULT_HTTP_APIS = [ 'eth', 'net', 'web3', 'debug', 'engine', 'admin' ]

	def __init__(
		self,
		gethBin: str,
		httpPort: int,
		chainId: int = DEV_CHAIN_ID,
		blockPeriod: int = DEV_BLOCK_PERIOD,
		gasLimit: int = DEV_GAS_LIMIT,
		httpApis: List[str] = DEFAULT_HTTP_APIS,
		connTimeout: int = 5,
		termTimeout: int = 10,
	):
		httpApisStr = ','.join(httpApis)
		cmd = [
			gethBin,
			'--networkid', chainId,
			'--dev',
			'--dev.gaslimit', gasLimit,
			'--dev.period',   blockPeriod,
			'--http',
			'--http.api', httpApisStr,
			'--http.port', httpPort,
		]
		super(GethDevNodeGuard, self).__init__(cmd=cmd, termTimeout=termTimeout)

		self.httpPort = httpPort
		self.connTimeout = connTimeout

		self.w3 = None
		self.devAccount = None

	def Start(self) -> None:
		super(GethDevNodeGuard, self).Start()

		connInterval = 0.5

		startTime = time.time()
		self.w3 = web3.Web3(
			web3.HTTPProvider(f'http://127.0.0.1:{self.httpPort}')
		)
		while not self.w3.is_connected():
			if time.time() - startTime >= self.connTimeout:
				raise RuntimeError('failed to connect to the Geth node')
			time.sleep(connInterval)

		self.devAccount = self.w3.eth.accounts[0]
		accBalance = self.w3.eth.get_balance(self.devAccount)
		accBalanceEth = self.w3.from_wei(accBalance, 'ether')
		self.logger.info(f'default account balance: {accBalanceEth:.2f} ETH')

	def Stop(self) -> None:
		super(GethDevNodeGuard, self).Stop()
		self.w3 = None

	def __enter__(self) -> 'GethDevNodeGuard':
		self.Start()
		return self

	def __exit__(self, exc_type, exc_value, traceback) -> None:
		self.Stop()

	def FillAccount(
		self,
		accAddr: str,
		amountWei: Union[int, None] = None,
		amountEth: Union[float, None] = None,
	) -> None:
		if amountWei is None and amountEth is None:
			raise ValueError('either amountWei or amountEth must be specified')
		if amountWei is not None and amountEth is not None:
			raise ValueError('only one of amountWei or amountEth can be specified')
		if amountWei is None:
			amountWei = self.w3.to_wei(amountEth, 'ether')

		self.logger.info(f'transferring {amountEth:.2f} ETH to {accAddr}...')

		tx = {
			'chainId': self.w3.eth.chain_id,
			'nonce': self.w3.eth.get_transaction_count(self.devAccount),
			'from': self.devAccount,
			'to': accAddr,
			'value': amountWei,
			'gas': 21000,
		}
		txHash = self.w3.eth.send_transaction(tx)

		receipt = self.w3.eth.wait_for_transaction_receipt(txHash)
		if receipt.status != 1:
			raise RuntimeError(f'transaction failed: {receipt}')

		balance = self.w3.eth.get_balance(accAddr)
		balanceEth = self.w3.from_wei(balance, 'ether')
		self.logger.info(f'account {accAddr} now has balance of {balanceEth:.2f} ETH')

