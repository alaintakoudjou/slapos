#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import os
import socket
import networkx as nx
import thread as th
import threading
import ast
import subprocess
import xml.dom.minidom
from os import waitpid, P_NOWAIT, WIFEXITED, WEXITSTATUS, WIFSIGNALED, WTERMSIG
from errno import ECHILD
import time

from MachineClass import MachineClass
from DataManager import DataManager

import signal
import logging
##
# Class Scheduler
# This class implements the behavior of a scheduler
###

class SchedulerClass(MachineClass):

    def __init__(
        self,
        application_file,
        host,
        cpu,
        mhz,
        syst,
        ram,
        disk,
        free,
        ):
       

        #
        # host: server Redis where we publish topics
        # meaning of other parameters is clear
        #

        m = MachineClass(
            cpu,
            mhz,
            syst,
            ram,
            disk,
            free,
            )



        #self.config = config
       
        logger = logging.getLogger("RedisDG-Scheduler")
        logger.setLevel(logging.INFO)
        #log_file = os.path.join(config.cwd, 'log', 'scheduler.log')
        log_file = 'log/scheduler.log'
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(file_handler)
        logger.info('Configured logging to file %r' % log_file)

        # Initilize the XML file which contains the application description
        #file = 'RedisDG.xml'

        doc = xml.dom.minidom.parse(application_file)

        #Corserver = doc.getElementsByTagName('CoreServer'
        #    )[0].childNodes[0].data
        #Dserver = doc.getElementsByTagName('DataServer'
        #    )[0].childNodes[0].data
        #Codserver = doc.getElementsByTagName('CodeServer'
        #    )[0].childNodes[0].data
        #Aserver = doc.getElementsByTagName('AccountingServer'
        #    )[0].childNodes[0].data
        
        Corserver = host
        Dserver = host
        Codserver = host
        Aserver = host
        #
        # DataManager instance
        #

        d = DataManager(Corserver, Dserver, Codserver, Aserver, 'MD5')

        # Extract Data from XML file : channels

        FT = doc.getElementsByTagName('FinishedTasks')[0].childNodes[0].data
        Em = doc.getElementsByTagName('Emergency')[0].childNodes[0].data
        WT = doc.getElementsByTagName('WaitingTasks')[0].childNodes[0].data
        TTD = doc.getElementsByTagName('TasksToDo')[0].childNodes[0].data
        TIP = doc.getElementsByTagName('TasksInProgress'
                                   )[0].childNodes[0].data
        TTV = doc.getElementsByTagName('TasksToVerify'
                                   )[0].childNodes[0].data
        SV = doc.getElementsByTagName('SelectVolunteers'
                                  )[0].childNodes[0].data
        VW = doc.getElementsByTagName('VolunteerWorkers'
                                  )[0].childNodes[0].data


        # Construire le liste des taches independantes: listracine
        racines = doc.getElementsByTagName('Racine')
        listracine=[]
        nods= doc.getElementsByTagName('Node')
        for r in racines:
			for nod in nods:
				if nod.getAttribute('nodeName') == r.childNodes[0].nodeValue:
					x = nod.getAttribute('nodeID')
			listracine.append(int(x))

        #
        # Code to initialise the subscription
        #

        rr = d.server.pubsub()
        rr.subscribe(WT)
        em = d.server.pubsub()
        em.subscribe(Em)

        #
        # We analyse the message
        #

        for msg in rr.listen():
            print 'scheduler receives the number of nodes in the Graph: ', \
                msg['data']
            cc = ast.literal_eval(msg['data'])
            break
        nb = 0
        dic = dict()
        for msg in rr.listen():
            #print 'scheduler receives: ', msg['data']
            logger.info('scheduler receives: %s' % msg['data'])
            c = ast.literal_eval(msg['data'])
            dic[c[0]] = c[1]
            nb = nb + 1
            if nb == cc:
                break
        print 'Scheduler is finishing with dictionary of predecessors:', \
            dic
        logger.info('Scheduler is finishing with dictionary of predecessors:' %dic)

        #
        # le  scheduler reste à l'ecoute des machines volontaire
        #

        pid1 = os.fork()
        if pid1 == 0:
            tt = d.server.pubsub()
            tt.subscribe(VW)
           

            MyDict = {}
            for mssg in tt.listen():

                # info is a tuple (x,y) : x= worker ID ; y= the task

                info = ast.literal_eval(mssg['data'])
                task = info[1]
                #print '&&&&&&&&', info
                if task not in MyDict.keys():
                    print 'Scheduler select the volunteer worker', \
                        mssg['data']
                    MyDict[task] = 'DONE'
                    d.server.publish(SV, info)
 
 
        #
        # The scheduler publish independant tasks
        #
            
        else:
            pid2 = os.fork()
            if pid2 == 0 : 
                ff = d.server.pubsub()
                ff.subscribe(FT)
                # generer la liste des racines du graphe dupliqué
                l=[]
                for i in listracine:
                    for j in range(int(doc.getElementsByTagName('CloneNumber')[0].childNodes[0].data)+1):
                        x= str(i)+'.'+str(j)
                        l.append(str(x))
                #print 'La liste des noeuds racines du graphe',l
                #l = ['4.0','4.1','6.0','6.1']
                for i in l:
					#print '((((((((((((( listracine', i
					d.server.publish(TTD, i)
                

                # waiting for new tasks without predecessors

                for msg1 in ff.listen():
                    print 'scheduler receives the finished task : ', \
                    msg1['data']
                    logger.info('scheduler receives the finished task : %s' %msg1['data'])
                    e = str(ast.literal_eval(msg1['data']))
                    try : 
                        del dic[e]
                    except:
                        print 'Error : Enable to delete from dictionary'
                        logger.info('Error : Enable to delete from dictionary')
                    for i in dic:
                        if e in dic[i]:
                            dic[i].remove(e)
                    #print '-------the dictionnary of tasks: ', dic, '----', \
                    #len(dic)
                    logger.info('-------the dictionnary of tasks:  ' %dic )
                    
                #raw_input('--> ')
                    for i in dic:
                        if dic[i] == [] and i not in l:
                            l.append(i)
                            d.server.publish(TTD, i)
                
                    if dic == {}:
                        d.server.publish(Em,'STOP')
                        print ' ........Emergency is activated'
                        logger.info(' ........Emergency is activated')
                    #sys.exit('scheduler exits')
                        break;
            else :
                em = d.server.pubsub()
                em.subscribe(Em)
                for s in em.listen():
                    pp = s['data']
                    if pp == 'STOP' :
                        #print '++++++++++++parent process (scheduler) listen to EMERGENCY',os.getpid()
                        logger.info('++++++++++++parent process (scheduler) listen to EMERGENCY %s' %os.getpid())
                        #time.sleep(3);
                        os.kill(pid1,signal.SIGKILL)
                        os.kill(pid2,signal.SIGKILL)
                        #print 'scheduler kills its child'
                        logger.info('scheduler kills its child')
                        print 'process scheduler terminated'
                        exit(12)
                        break
        

