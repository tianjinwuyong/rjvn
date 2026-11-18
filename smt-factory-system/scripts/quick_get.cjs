const http = require('http');

function get(path) {
  return new Promise((resolve, reject) => {
    console.log('GET', path);
    const req = http.get({ hostname: 'localhost', port: 8080, path, headers: { Accept: 'application/json' } }, res => {
      console.log('Status:', res.statusCode);
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => { console.log('Body:', body.substring(0, 500)); resolve(body); });
    });
    req.on('error', e => { console.error('Error:', e.message); reject(e); });
    req.setTimeout(5000, () => { req.destroy(); console.log('Timeout'); });
  });
}

async function main() {
  await get('/api/dispatch/sessions');
  await get('/api/wms/shelf/list');
}

main().catch(e => console.error(e.message));
