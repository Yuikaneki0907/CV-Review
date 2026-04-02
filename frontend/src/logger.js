/**
 * Structured console logger for CV-Review frontend.
 *
 * Usage:
 *   import logger from './logger';
 *   logger.info('Logged in', { email: 'x@y.com' });
 *   logger.error('API failed', { status: 500, url: '/api/...' });
 */

const LEVELS = { DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3 };
const LOG_LEVEL = LEVELS[import.meta.env.VITE_LOG_LEVEL?.toUpperCase()] ?? LEVELS.DEBUG;

const ERROR_BUFFER_KEY = 'cv_review_error_log';
const MAX_BUFFER = 100;

function _ts() {
  return new Date().toISOString();
}

function _write(level, levelName, args) {
  if (level < LOG_LEVEL) return;

  const prefix = `[${_ts()}] [${levelName}]`;

  switch (level) {
    case LEVELS.ERROR:
      console.error(prefix, ...args);
      break;
    case LEVELS.WARN:
      console.warn(prefix, ...args);
      break;
    case LEVELS.INFO:
      console.info(prefix, ...args);
      break;
    default:
      console.debug(prefix, ...args);
  }

  // Buffer errors in sessionStorage for export
  if (level >= LEVELS.ERROR) {
    try {
      const buf = JSON.parse(sessionStorage.getItem(ERROR_BUFFER_KEY) || '[]');
      buf.push({ ts: _ts(), level: levelName, msg: args.map(String).join(' ') });
      if (buf.length > MAX_BUFFER) buf.splice(0, buf.length - MAX_BUFFER);
      sessionStorage.setItem(ERROR_BUFFER_KEY, JSON.stringify(buf));
    } catch {
      // sessionStorage full or unavailable — ignore
    }
  }
}

const logger = {
  debug: (...args) => _write(LEVELS.DEBUG, 'DEBUG', args),
  info:  (...args) => _write(LEVELS.INFO,  'INFO',  args),
  warn:  (...args) => _write(LEVELS.WARN,  'WARN',  args),
  error: (...args) => _write(LEVELS.ERROR, 'ERROR', args),

  /** Export buffered errors (useful for bug reports). */
  exportErrors: () => {
    try {
      return JSON.parse(sessionStorage.getItem(ERROR_BUFFER_KEY) || '[]');
    } catch {
      return [];
    }
  },
};

export default logger;
