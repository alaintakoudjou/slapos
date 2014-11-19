def setArguments():
  usage = "usage: %s [options]" % sys.argv[0]
  config = Parser(usage=usage).check_args()
  logger.setLevel(logging.INFO)
  if config.console:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(console_handler)
  if config.log_file:
    if not os.path.isdir(os.path.dirname(config.log_file)):
      # fallback to console only if directory for logs does not exists and
      # continue to run
      raise ValueError('Please create directory %r to store %r log file' % (
        os.path.dirname(config.log_file), config.log_file))
    else:
      file_handler = logging.FileHandler(config.log_file)
      file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
      logger.addHandler(file_handler)
      logger.info('Configured logging to file %r' % config.log_file)
  if config.pid_file:
    if not os.path.isdir(os.path.dirname(config.pid_file)):
      raise ValueError('Please create directory %r to store %r pid file' % (
        os.path.dirname(config.pid_file), config.pid_file))
    else:
      open(config.pid_file, 'w').write(str(os.getpid()))
  if config.directory:
    if not os.path.isdir(config.directory):
      raise ValueError('Please create directory %r to store local files' % (
        config.directory))
    else:
      os.chdir(config.directory)
  config.cwd = os.getcwd()

  return config
