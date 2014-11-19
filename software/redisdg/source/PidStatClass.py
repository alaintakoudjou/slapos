#!/usr/bin/python
# -*- coding: utf-8 -*-

import zlib
import sys
import os
import socket
import MyRedis2410 as redis
import networkx as nx
import thread as th
import threading
import random
import ast
import subprocess
import xml.dom.minidom
from os import waitpid, P_NOWAIT, WIFEXITED, WEXITSTATUS, WIFSIGNALED, WTERMSIG
from errno import ECHILD
from multiprocessing import Pool
from multiprocessing import Process, Lock

from MachineClass import MachineClass
from DataManager import DataManager
#from PidStatClass import PidStatClass

import signal
import logging

class PidStatClass:
    def __init__(self, pid):
        
        #args=["pidstat","-p",str(pid),"-h","-u","-T","CHILD","-r","4"]
        args=["pidstat","-p",str(pid)]
	p1 = subprocess.Popen(args,stdout=subprocess.PIPE,shell=False)
	#
	# on recupere la sortie et on l'envoie pour l'accounting
	#
	preprocessed1, _ = p1.communicate()
	p1.stdout.close()
        prepro = preprocessed1.split('\n')
	#
	# il faudra utiliser Redis pour stoker sur le serveur
	#
        #p = Pool(5)
	#p.acquire()
	logging.info(preprocessed1)
	#p.release()
	#print '=> ',prepro
	#os._exit(0)
