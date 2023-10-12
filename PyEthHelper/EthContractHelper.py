#!/usr/bin/env python3
# -*- coding:utf-8 -*-
###
# Copyright (c) 2023 Haofan Zheng
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.
###


import json
import logging
import os
import urllib.request
import web3

from eth_account.datastructures import SignedTransaction
from typing import Any, Callable, Dict, List, Tuple, Union
from web3 import Web3 # python3 -m pip install web3
from web3.contract.contract import Contract, ContractConstructor, ContractFunction
from web3.types import TxReceipt

# check web3 version
if list(map(int, web3.__version__.split('.'))) < [ 6, 2, 0 ]:
	raise RuntimeError(
		'web3 version {} is not supported; '
		'please upgrade to version 6.2.0 or above.'.format(web3.__version__)
	)


def LoadBytesFromRelease(
	projConf: dict,
	release: str,
	contract: str
) -> Tuple[str, str]:

	urlAbi = projConf['releaseUrl'].format(version=release, contract=contract + '.abi')
	with urllib.request.urlopen(urlAbi) as f:
		abiBytes = f.read().decode()

	urlBin = projConf['releaseUrl'].format(version=release, contract=contract + '.bin')
	with urllib.request.urlopen(urlBin) as f:
		binBytes = f.read().decode()

	return abiBytes, binBytes


def LoadBytesFromLocal(
	projConf: Union[dict, Tuple[str, str]],
	contract: str
) -> Tuple[str, str]:

	if isinstance(projConf, tuple):
		pathAbi, pathBin = projConf
	else:
		module = projConf['contractModuleMap'][contract]
		pathAbi = os.path.join(projConf['buildDir'], module, contract + '.abi')
		pathBin = os.path.join(projConf['buildDir'], module, contract + '.bin')

	if os.path.isfile(pathAbi) is False:
		raise FileNotFoundError(
			'Cannot find locally built contract ABI file at {}; '
			'please build the contract first.'.format(pathAbi)
		)

	with open(pathAbi, 'r') as f:
		abiBytes = f.read()

	if os.path.isfile(pathBin) is False:
		raise FileNotFoundError(
			'Cannot find locally built contract BIN file at {}; '
			'please build the contract first.'.format(pathBin)
		)

	with open(pathBin, 'r') as f:
		binBytes = f.read()

	return abiBytes, binBytes


def LoadContract(
	w3: Web3,
	projConf: Union[ dict, tuple, os.PathLike ],
	contractName: str,
	release: Union[ None, str ] = None,
	address: Union[ None, str ] = None,
) -> Contract:

	if isinstance(projConf, tuple):
		pass
	elif isinstance(projConf, dict):
		pass
	else:
		with open(projConf, 'r') as f:
			projConf = json.load(f)

	if release is None:
		# load from local build
		abiBytes, binBytes = LoadBytesFromLocal(projConf, contractName)
	else:
		# load from release
		abiBytes, binBytes = LoadBytesFromRelease(projConf, release, contractName)

	if address is None:
		# deploy new contract
		contract = w3.eth.contract(abi=abiBytes, bytecode=binBytes)
	else:
		# load existing contract
		contract = w3.eth.contract(address=address, abi=abiBytes)

	return contract


def _EstimateGas(
	executable: Union[ ContractConstructor, ContractFunction ],
	value: int,
) -> int:
	logger = logging.getLogger(__name__ + '.' + _EstimateGas.__name__)

	gas = executable.estimate_gas({
		'value': value,
	})
	logger.info('Estimated gas: {}'.format(gas))
	# add a little bit flexibility
	gas = int(gas * 1.1)

	return gas


def _DetermineGas(
	executable: Union[ ContractConstructor, ContractFunction ],
	gas: Union[ None, int ],
	value: int,
) -> int:
	logger = logging.getLogger(__name__ + '.' + _DetermineGas.__name__)

	if gas is None:
		gas = _EstimateGas(executable, value)

	logger.debug('Gas: {}; Value: {}'.format(gas, value))

	return gas


def DefaultFeeCalculator(
	ethGasPrice: int,
	ethMaxPriorityFee: int,
) -> Tuple[int, int]:
	# determine max priority fee
	# priority fee is 2% of base fee
	maxPriorFee = (ethGasPrice * 2) // 100
	# ensure it's higher than w3.eth.max_priority_fee
	maxPriorFee = max(maxPriorFee, ethMaxPriorityFee)

	return maxPriorFee, ethGasPrice + maxPriorFee


def _FillMessage(
	w3: Web3,
	gas: int,
	value: int,
	privKey: Union[ None, str ],
	feeCalculator: Callable[[int, int], Tuple[int, int]],
) -> dict:

	msg = {
		'nonce': w3.eth.get_transaction_count(w3.eth.default_account),
		'chainId': w3.eth.chain_id,
		'gas': gas,
		'value': value,
	}
	if privKey is not None:
		maxPrioriyFee, maxFee = feeCalculator(
			ethGasPrice=int(w3.eth.gas_price),
			ethMaxPriorityFee=int(w3.eth.max_priority_fee),
		)
		msg['maxPriorityFeePerGas'] = maxPrioriyFee
		msg['maxFeePerGas'] = maxFee

	return msg


def _SignTx(
	w3: Web3,
	tx: dict,
	privKey: str,
	confirmPrompt: bool
) -> SignedTransaction:
	logger = logging.getLogger(__name__ + '.' + _SignTx.__name__)

	maxBaseFee = tx['maxFeePerGas']
	maxPriorityFee = tx['maxPriorityFeePerGas']
	gas = tx['gas']
	value = tx['value']

	balance = w3.eth.get_balance(w3.eth.default_account)

	maxFee = (maxBaseFee + maxPriorityFee) * gas
	maxCost = maxFee + value
	if maxCost > balance:
		raise RuntimeError(
			'Insufficient balance to pay for the transaction'
			'(balance {} wei; max cost: {} wei)'.format(
				balance, maxCost
			)
		)

	if confirmPrompt:
		baseFee = w3.eth.gas_price
		baseFeeGwei = w3.from_wei(baseFee, 'gwei')
		fee = baseFee * gas
		feeGwei = w3.from_wei(fee, 'gwei')

		maxBaseFeeGwei = w3.from_wei(maxBaseFee, 'gwei')
		maxPriorityFeeGwei = w3.from_wei(maxPriorityFee, 'gwei')
		maxFeeGwei = w3.from_wei(maxFee, 'gwei')

		valueEther = w3.from_wei(value, 'ether')

		cost = fee + value
		costEther = w3.from_wei(cost, 'ether')
		maxCostEther = w3.from_wei(maxCost, 'ether')

		balanceEther = w3.from_wei(balance, 'ether')
		afterBalanceEther = w3.from_wei(balance - cost, 'ether')
		minAfterBalanceEther = w3.from_wei(balance - maxCost, 'ether')

		print('Gas:                  {}'.format(gas))
		print('gas price:            {:.9f} Gwei'.format(baseFeeGwei))
		print('Fee:                  {:.9f} Gwei'.format(feeGwei))
		print('Max fee / gas:        {:.9f} Gwei'.format(maxBaseFeeGwei))
		print('Max prior. fee / gas: {:.9f} Gwei'.format(maxPriorityFeeGwei))
		print('Max fee:              {:.9f} Gwei'.format(maxFeeGwei))
		print('Value:                {:.18f} Ether'.format(valueEther))
		print()
		print('Cost:                 {:.18f} Ether'.format(costEther))
		print('Max cost:             {:.18f} Ether'.format(maxCostEther))
		print()
		print('Balance:              {:.18f} Ether'.format(balanceEther))
		print('After balance:        {:.18f} Ether'.format(afterBalanceEther))
		print('Min. after balance:   {:.18f} Ether'.format(minAfterBalanceEther))

		confirm = input('Confirm transaction? (please type "yes", case insensitive): ')
		if confirm.lower() != 'yes':
			raise RuntimeError('Transaction cancelled')

	logger.info(
		'Signing transaction with max cost of {} wei'.format(maxCost)
	)
	signedTx = w3.eth.account.sign_transaction(tx, privKey)

	return signedTx


def _DoTransaction(
	w3: Web3,
	executable: Union[ ContractConstructor, ContractFunction ],
	privKey: Union[ None, str ],
	gas: Union[ None, int ],
	value: int,
	confirmPrompt: bool,
	feeCalculator: Callable[[int, int], Tuple[int, int]],
) -> TxReceipt:
	logger = logging.getLogger(__name__ + '.' + _DoTransaction.__name__)

	gas = _DetermineGas(executable, gas, value)
	msg = _FillMessage(w3, gas, value, privKey, feeCalculator)

	if privKey is None:
		# no signing needed
		txHash = executable.transact(msg)
	else:
		# need to sign
		tx = executable.build_transaction(msg)
		signedTx = _SignTx(w3, tx, privKey, confirmPrompt)
		txHash = w3.eth.send_raw_transaction(signedTx.rawTransaction)

	receipt = w3.eth.wait_for_transaction_receipt(txHash)

	receiptJson = json.dumps(json.loads(Web3.to_json(receipt)), indent=4)
	logger.info('Transaction receipt: {}'.format(receiptJson))

	logger.info('Balance after transaction: {} Ether'.format(
		w3.from_wei(
			w3.eth.get_balance(w3.eth.default_account),
			'ether'
		)
	))

	return receipt


def _FindConstructorAbi(
	abiList: List[ dict ],
) -> dict:
	for abi in abiList:
		if abi['type'] == 'constructor':
			return abi

	raise ValueError('No constructor found in ABI')


def DeployContract(
	w3: Web3,
	contract: Contract,
	arguments: list,
	privKey: Union[str, None] = None,
	gas: Union[int, None] = None,
	value: int = 0,
	confirmPrompt: bool = True,
	feeCalculator: Callable[[int, int], Tuple[int, int]] = DefaultFeeCalculator,
) -> TxReceipt:
	logger = logging.getLogger(__name__ + '.' + DeployContract.__name__)

	constrAbi = _FindConstructorAbi(contract.abi)
	isPayable = constrAbi['stateMutability'] == 'payable'
	executable = contract.constructor(*arguments)

	receipt = _DoTransaction(
		w3=w3,
		executable=executable,
		privKey=privKey,
		gas=gas,
		value=value if isPayable else 0,
		confirmPrompt=confirmPrompt,
		feeCalculator=feeCalculator,
	)
	logger.info('Contract deployed at {}'.format(receipt.contractAddress))

	return receipt


def _FindFuncAbi(
	abiList: List[ dict ],
	funcName: str,
) -> dict:
	for abi in abiList:
		if (
			(abi['type'] == 'function') and
			(abi['name'] == funcName)
		):
			return abi

	raise ValueError('Function "{}" not found in ABI'.format(funcName))


def CallContractFunc(
	w3: Web3,
	contract: Contract,
	funcName: str,
	arguments: list,
	privKey: Union[str, None] = None,
	gas: Union[int, None] = None,
	value: int = 0,
	confirmPrompt: bool = True,
	feeCalculator: Callable[[int, int], Tuple[int, int]] = DefaultFeeCalculator,
) -> Union[TxReceipt, Any]:
	logger = logging.getLogger(__name__ + '.' + CallContractFunc.__name__)

	funcAbi = _FindFuncAbi(contract.abi, funcName)
	isViewFunc = funcAbi['stateMutability'] == 'view'
	isPayable = funcAbi['stateMutability'] == 'payable'
	executable = contract.functions[funcName](*arguments)

	if isViewFunc:
		logger.info('Calling view function "{}"'.format(funcName))
		result = executable.call()
		logger.info('Type:{}; Result: {}'.format(type(result), result))

		return result
	else:
		receipt = _DoTransaction(
			w3=w3,
			executable=executable,
			privKey=privKey,
			gas=gas,
			value=value if isPayable else 0,
			confirmPrompt=confirmPrompt,
			feeCalculator=feeCalculator,
		)

		return receipt


def ConvertValToWei(val: int, unit: str) -> int:
	logger = logging.getLogger(__name__ + '.' + ConvertValToWei.__name__)

	valueToSend = Web3.to_wei(val, unit)
	valueToSendEth = Web3.from_wei(valueToSend, 'ether')
	if valueToSend > 0:
		logger.warning(
			'Value to be sent: {:.18f} ether (or {} wei)'.format(
				valueToSendEth,
				valueToSend
			)
		)

	return int(valueToSend)


def _LoadAccountCredentials(
	keyJson: os.PathLike,
	index: int
) -> Tuple[str, str]:
	with open(keyJson, 'r') as f:
		keyJson: Dict[str, Dict[str, str]] = json.load(f)

	if index >= len(keyJson['addresses']):
		raise IndexError('Cannot find address at index {}'.format(index))

	address = [
		a for i, a in enumerate(keyJson['addresses'].keys()) if i == index
	][0]

	for addr, priv in keyJson['private_keys'].items():
		if addr.lower() == address.lower():
			return address, priv

	raise KeyError('Cannot find private key for address {}'.format(address))


def SetupSendingAccount(
	w3: Web3,
	account: int,
	keyJson: Union[ None, os.PathLike ] = None,
) -> Union[ str, None ]:
	logger = logging.getLogger(__name__ + '.' + SetupSendingAccount.__name__)

	if keyJson is not None:
		addr, privKey = _LoadAccountCredentials(keyJson, account)
		w3.eth.default_account = addr
	else:
		w3.eth.default_account = w3.eth.accounts[0]
		privKey = None

	if privKey is not None:
		# ensure that the private key matches the address
		privAcc = w3.eth.account.from_key(privKey)
		if privAcc.address != w3.eth.default_account:
			raise ValueError(
				'The private key does not match the address'
			)

	logger.info(
		'The address of the account to be used: {}'.format(
			w3.eth.default_account
		)
	)

	return privKey

