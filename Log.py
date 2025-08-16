import os
from .Settings import Settings

USER_HOME = os.path.expanduser('~')
LOG_DIRECTORY = USER_HOME+"/Documents/Ableton/User Library/Remote Scripts"
LOG_FILE = LOG_DIRECTORY + "/log.txt"

if Settings.LOGGING:
    try:
        # First try with exist_ok parameter (Python 3)
        os.makedirs(LOG_DIRECTORY, exist_ok=True)
    except TypeError:
        # Fallback for older Python versions
        try:
            os.makedirs(LOG_DIRECTORY)
        except OSError as e:
            # Check if the error is because the directory already exists
            import errno
            if e.errno != errno.EEXIST:
                raise
    
    try:
        with open(LOG_FILE, 'a') as f:
            f.write('====================\n')
            f.write('Logging initialized\n')
    except Exception as e:
        # Try to write to a fallback location
        try:
            fallback_log = USER_HOME + "/launchpad95_log.txt"
            with open(fallback_log, 'a') as f:
                f.write(f"Error initializing log: {str(e)}\n")
        except:
            pass  # If all logging fails, silently continue

log_num = 0

def log(message):
    global log_num
    if Settings.LOGGING:
        try:
            with open(LOG_FILE, 'a') as f:
                if type(message) == list:
                    message = '\n'.join(message)
                f.write(str(log_num) + ' ' + str(message) + '\n')
            log_num += 1
        except Exception as e:
            # If logging fails, try to write to a fallback location
            try:
                fallback_log = USER_HOME + "/launchpad95_log.txt"
                with open(fallback_log, 'a') as f:
                    f.write(f"Error logging: {str(e)}\n")
                    f.write(str(log_num) + ' ' + str(message) + '\n')
            except:
                pass  # If all logging fails, silently continue