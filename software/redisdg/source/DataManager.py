#!/usr/bin/python
# -*- coding: utf-8 -*-
import zlib
import sys
import os
import shlex
import MyRedis2410 as redis
import random
import ast
import subprocess
import stat
import hashlib

import signal
import logging

import time
import datetime

import xml.dom.minidom


class ServerClass:

    # ##
    # There are 4 possibilities for servers: the main server for 
    # the protocol itself (CoreServer),
    # the data server storing input/output data for the applications,
    # CodeServer which is the name of the server for retreiving codes
    # and the accounting server where we store the 'invoice' (resource
    # consumed by the workers)
    # Note also that the Redis databases are different for each server.
    # ##

    CoreServer       = None
    DataServer       = None
    CodeServer       = None
    AccountingServer = None
    typeintegrety    = None

    def __init__(
        self,
        Core='localhost',
        Data='localhost',
        Code='localhost',
        Accounting='localhost',
        tip='MD5',
        ):
        self.CoreServer = redis.Redis(host=Core, port=6379, db=0)
        self.DataServer = redis.Redis(host=Data, port=6379, db=1)
        self.CodeServer = redis.Redis(host=Code, port=6379, db=2)
        self.AccountingServer = redis.Redis(host=Accounting, port=6379, db=3)

        # Now, the integrety of files

        if ['MD5'].__contains__(tip):
            self.typeintegrity = tip


class DataManager(ServerClass):

    server = None
    server_d = None
    server_a = None

    def __init__(
        self,
        Core='localhost',
        Data='localhost',
        Code='localhost',
        Accounting='localhost',
        tip='MD5'
        ):

        s = ServerClass(Core, Data, Code, Accounting, tip)
        self.server = s.CodeServer
        self.server_d = s.DataServer
        self.server_a = s.AccountingServer


    # ##
    # List all the file name stored in the DataServer
    # ##

    def ListFileName(self):

        #self.config = config
        logger = logging.getLogger("RedisDG-Main")
        logger.setLevel(logging.INFO)
        #log_file = os.path.join(config.cwd, 'log', 'broker.log')
        log_file = 'log/main.log'
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(file_handler)
        logger.info('Configured logging to file %r' % log_file)



        #print 'File(s) on DataServer: ', self.server_d.keys('*')
        #print 'File(s) on CodeServer: ', self.server.keys('*')
        logger.info('File(s) on DataServer: ' %self.server_d.keys('*'))
        logger.info('File(s) on CodeServer: ' %self.server.keys('*'))

    # ##
    # Load a file into a Redis Server
    # ##

    def LoadFileIntoRedis(self, filename, mytype):
        f = open(filename, 'r')
        mystr = f.read()
        res = zlib.compress(mystr)
        if mytype == 'CODE':
            self.server.append(filename, res)
        else:
            self.server_d.append(filename, res)
        f.close()

    # ##
    # Store a raw file (no compression) into a Redis Server
    # under the name (key) label. The Redis server to use
    # is distinguished by 'mytype'
    # ##

    def StoreRawFileIntoRedis(self, label, filename, mytype):
        f = open(filename, 'r')
        res = f.read()
        f.close()
        if mytype == 'CODE':
            self.server.append(label, res)
        elif mytype == 'ACCOUNTING':
            self.server_a.append(label, res)
        elif mytype == 'DATA':
            self.server_d.append(label, res)
        else:
            raise 'Type error in StoreRawFileIntoRedis function'

    # ##
    # Execute locally a file stored in the CodeServer
    # The code do not require any parameter and the result
    # is not stored
    # ##

    def ExecFileFromRedis(self, filename):
        mystr = self.server.get(filename)
        if mystr != None:
            res = zlib.decompress(mystr)
            f = open(filename, 'r+w+x')
            f.write(res)
            f.close()
            p = subprocess.Popen(args=[], executable=filename,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, shell=True)
            outputlines = p.stdout.readlines()
            p.wait()
            #print outputlines
            logger.info(outputlines)
        else:
            raise 'error trying to execute ', filename, \
                ' in ExecFileFromRedis'

    # ##
    # Execute locally a command that specify arguments on the command line
    # The first name of the command_line is the file name
    # The output_file parameter is the name of the outfile: we store the
    # result in the Redis server.
    # Command line format: 'python essai.py 'bonjour' 'a vous' 'tous'
    # ##

    def ExecCommandLineFromRedis(self, command_line, output_file):
        args = shlex.split(command_line)
        filename = args[1]  # args[1] = 'python', we assume that args[0]=/bin/bash or perl or python...
        mystr = self.server.get(filename)
        if mystr != None:
            res = zlib.decompress(mystr)

            # we dump the code on the local disk

            filout = open(filename, 'w')
            filout.write(res)
            filout.close()

            # we start the execution

            out = subprocess.check_output(args)

            #            sts = os.waitpid(p.pid, 0)[1]
            # we compress and we store the result into Redis

            res = zlib.compress(out)
            self.server_d.append(output_file, res)

            # we remove the Python source file

            os.remove(filename)
        else:
            raise 'error trying to execute ', filename, \
                ' in ExecCommandLineFromRedis'

    # ##
    # Execute locally a code.
    # First we download the code, then the input files
    # Second we execute the code
    # Third we store the output file into the Redis server
    # At least we remove the files to clean the partition
    # ##

    def ExecCodeFromRedis(
        self,
        language,
        code_name,
        list_input_files,
        list_output_files,
        ):

        # We download source/exec file

        #print 'ExecCodeFromRedis: ', code_name, ' ', list_input_files, \
        #    ' ', list_output_files
        mystr = self.server.get(code_name)
        if mystr != None:
            res = zlib.decompress(mystr)
            info = random.randint(1, 10000)

            # we make unique the file name

            filout = open('tmp/' + str(info) + code_name, 'w')
            filout.write(res)
            filout.close()
            os.chmod('tmp/' + str(info) + code_name, stat.S_IRWXU)

        # we download the input files

        for filename in list_input_files:
            mystr = self.server_d.get(filename)
            if mystr != None:
                res = zlib.decompress(mystr)
                filout = open('tmp/' + filename, 'w')
                filout.write(res)
                filout.close()
            else:
                self.ListFileName()
                print 'error trying to execute ', filename, \
                    ' in ExecCodeFromRedis'
                raise 'error trying to execute in ExecCodeFromRedis'

        # we start the execution

        input_files = ''
        for f in list_input_files:
            input_files = input_files + ' ' + 'tmp/' + f
        output_files = ''
        for f in list_output_files:
            output_files = output_files + ' ' + 'tmp/' + f
        Myargs = language + ' ' + 'tmp/' + str(info) + code_name + ' ' \
            + input_files + ' ' + output_files
        #print 'Args: ', Myargs
       
        
        p = subprocess.Popen(['tmp/' + str(info) + code_name + ' '
                             + input_files + ' ' + output_files],
                             shell=True, executable='/bin/bash')
        p.wait()

        # We store the output files into the Redis DataServer

        for filename in list_output_files:
            f = open('tmp/' + filename, 'r')
            mystr = f.read()
            res = zlib.compress(mystr)
            self.server_d.append(filename, res)
            f.close()
        #print 'File located on Data and Code servers'
        self.ListFileName()


        # we remove the Python source file, the input and output files
        # os.remove('/tmp/'+str(info)+code_name)
        #
        # Attention a ce remove
        #
        # for f in list_input_files:
            # os.remove('/tmp/'+f)
        # for f in list_output_files:
            # os.remove('/tmp/'+f)



    def ExecCodeFromRedis_Pegasus(
        self,
        list_input_files,
        list_output_files,
        code,
        #runtime
        argument,
	Dserver
        ):
		
		
		#pour povoir extraire les sizes des fichiers input output
		
		#doc = xml.dom.minidom.parse('RedisDG.xml')
		
        #Verifier si la liste des inputs et vide, et puis 
        #télécharger les fichiers du serveur et les ouvrir en lecture
        
        #for filename in list_output_files:
            #f = open('tmp/' + filename, 'w')
            #f = open(filename, 'a+')
            #f.write('bonjour')
            #f.close()
		
        if list_input_files != []:
            #print '+++++++++++++listinput++++++++++++++++++++', list_input_files
            for filename in list_input_files:
                #mystr = self.server_d.get(filename)
                #if mystr != None:
                    #res = zlib.decompress(mystr)
                    #f = open('tmp/' + filename, 'w')
                    #f = open(filename, 'w')
                    #f.write(res)
                    #f.close()
                 if os.path.lexists(filename)== False:
                    #os.system('rm -r  '+filename)
               
                    cmd="wget http://"+Dserver+"/164-job/"+filename
                    os.system(cmd)


        # We download source/exec file
        ####cmd="wget http://"+Dserver+"/164-job/"+code
        ####os.system(cmd)

        #print 'ExecCodeFromRedis: ', code_name, ' ', list_input_files, \
        #    ' ', list_output_files
#        mystr = self.server.get(code)
#        if mystr != None:
#            res = zlib.decompress(mystr)
#            filout = open('/tmp/' + code, 'w')
#            filout.write(res)
#            filout.close()
#            os.chmod('/tmp/'+ code, stat.S_IRWXU)





        
        p1 = subprocess.Popen([ 'export PATH=$PATH:.' ], shell=True, executable='/bin/bash')
        # we start the execution
        #time.sleep(float(runtime))            
        print 'The command to run is : ', code+' '+argument
        p = subprocess.Popen([ code+' '+argument ], shell=True, executable='/bin/bash')        
        p.wait()
        #compilation=os.system('gcc Montage/'+code+'.c')    
                
        # We store the output files into the Redis DataServer

        for filename in list_output_files:
            #f = open('tmp/' + filename, 'w')
            cmd="sshpass -p'grid5000' scp -o StrictHostKeyChecking=no "+filename+" "+Dserver+":/var/www/164-job/"
            #cmd="scp "+filename+" root@"+Dserver+":/var/www/164-job/"
            os.system(cmd)
            #f = open(filename, 'a+')
            #f.write('bonjour')
            #f.close()
            #f = open('tmp/' + filename, 'r')
            #f = open( filename, 'r')
            #mystr = f.read()
            #res = zlib.compress(mystr)
            #self.server_d.append(filename, res)
            #f.close()
        #print 'File located on Data and Code servers'
        self.ListFileName()
		