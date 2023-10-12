#!/usr/bin/env python3
# -*- coding:utf-8 -*-
###
# Copyright (c) 2023 Haofan Zheng
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.
###


from setuptools import setup
from setuptools import find_packages

import PyEthHelper._Meta


setup(
	name        = PyEthHelper._Meta.PKG_NAME,
	version     = PyEthHelper._Meta.__version__,
	packages    = find_packages(where='.', exclude=['main.py']),
	url         = 'https://github.com/lsd-ucsc/PyEthHelper',
	license     = PyEthHelper._Meta.PKG_LICENSE,
	author      = PyEthHelper._Meta.PKG_AUTHOR,
	description = PyEthHelper._Meta.PKG_DESCRIPTION,
	entry_points= {
		'console_scripts': [
			'PyEthHelper=PyEthHelper.__main__:main',
		]
	},
	install_requires=[
		'web3>=6.2.0',
	],
)
