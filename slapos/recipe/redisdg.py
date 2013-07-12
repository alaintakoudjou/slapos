##############################################################################
#
# Copyright (c) 2010 Vifib SARL and Contributors. All Rights Reserved.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsibility of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# guarantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################
from slapos.recipe.librecipe import GenericBaseRecipe
import os
import subprocess
import zc.buildout
import filecmp
import urlparse
import shutil
import sys
import json

class Recipe(GenericBaseRecipe):
  
  def copy_file(self, source, dest):
    """"Copy file with source to dest with auto replace
        return True if file has been copied and dest ha been replaced
    """
    result = False
    if source and os.path.exists(source):
      if os.path.exists(dest):
        if filecmp.cmp(dest, source):
          return False
        os.unlink(dest)
      result = True
      shutil.copy(source, dest)
    return result
  
  def download(self, url, filename=None, md5sum=None):
    if not url.startswith('http') or not url.startswith('ftp'):
      return url
    cache = os.path.join(self.options['rootdirectory'].strip(), 'tmp')
    if not os.path.exists(cache):
      os.mkdir(cache)
    downloader = zc.buildout.download.Download(self.buildout['buildout'],
                    hash_name=True, cache=cache)
    path, _ = downloader(url, md5sum)
    if filename:
      name = os.path.join(cache, filename)
      os.rename(path, name)
      return name
    return path
  
  def install(self):
    path_list = []
    environ = os.environ
    rootdir = self.options['root-dir'].strip()
    workdir = self.options['work-directory'].strip()
    if self.options['deamon'].strip() == "manager":
      deamon = "broker,scheduler,checker,monitor"
    elif self.options['deamon'].strip() == "worker":
      deamon = "worker"
    else:
      deamon = "broker,scheduler,checker,monitor,worker"
    environ['PATH'] = os.pathsep.join([os.path.join(rootdir, 'bin'), 
                                                          os.environ['PATH']])
    for f in os.listdir(self.options['eggs-directory'].strip()):
      dir = os.path.join(self.options['eggs-directory'].strip(), f)
      if os.path.isdir(dir) and "networkx" in f:
        if environ['PYTHONPATH']:
          environ['PYTHONPATH'] = dir + ":" + environ['PYTHONPATH']
        else:
          environ['PYTHONPATH'] = dir
        break
    logfile = self.options['log-file'].strip()
    tmpdir = self.options['tmp-dir'].strip()
    python = os.path.join(rootdir, 'bin/python')
    if not os.path.exists(python):
      os.symlink(self.options['python-bin'].strip(), python)   
    
    #copy all files to install directory
    desc = json.loads(self.options['job-desc'])
    configXml = os.path.join(workdir, 'config.xml')
    self.copy_file(self.download(desc['config']), configXml)
    for file in desc['files']:
      tmp_name = os.path.join(workdir, file)
      if os.path.exists(tmp_name):
        os.unlink(tmp_name)
      os.symlink(self.download(desc['files'][file], file), tmp_name)
    
    #generate python wrapper script
    redisdg = self.options['wrapper'].strip()
    args = [self.options['redisdg-script'].strip(), 
            "-l", logfile, '-i', self.options['pid-file'], 
            '-s', self.options['redis'].strip(),
            '-r', workdir, '-d', deamon]
    exe_wrapper = self.createPythonScript(redisdg,
        'slapos.recipe.librecipe.execute.executee',
        (args, environ)
    )
    path_list.append(exe_wrapper)
        
    