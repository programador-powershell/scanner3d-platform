/**
 * blender_live_bridge.js
 * Node.js client for the claude-blender-designer live bridge (and compatible).
 *
 * Mirrors the protocol from claude_bridge.py + bridge_cmd.py:
 *   - TCP localhost on 9877..9881 (first free wins on server)
 *   - Newline-delimited JSON: send {"code": "bpy python here", "shot": bool}
 *   - Receive {"ok": bool, "out": "stdout+err capped", "shot": "base64-png" | "SHOT_ERR:.."}
 *   - Robust discovery: .bridge_port cache file + quick probe ping
 *
 * Usage in server.js:
 *   const bridge = require('./lib/blender_live_bridge');
 *   const port = await bridge.discoverPort();
 *   const r = await bridge.execCode("import bpy; print(bpy.context.scene.name)", true);
 *   // r.out , r.shot (base64), r.ok
 *
 * To enable during character stage builds:
 *   set env BLENDER_LIVE_BRIDGE=1
 *   (requires a Blender GUI running with claude_bridge.py executed in Text Editor)
 *
 * The live bridge lets the platform:
 *   - drive construction *visibly* in the user's open Blender (real-time viewport)
 *   - capture live viewport shots (perfect for VLM garment judge / progress feedback)
 *   - do incremental corrections instead of one-shot headless only
 */

const net = require('net');
const fs = require('fs');
const path = require('path');

const PORTS = [9877, 9878, 9879, 9880, 9881];
const MCP_PORT = 9876;
const DEFAULT_PORTCACHE = path.join(__dirname, '..', 'data', '.blender_live_port');
const SHOT = path.join(__dirname, '..', 'data', 'live_shot.png');

function isMcpMode() {
  return (process.env.BLENDER_BRIDGE_MODE || 'socket').toLowerCase() === 'mcp';
}

function getPortCache() {
  // Allow pointing at claude-blender-designer work/ or custom
  return process.env.BLENDER_LIVE_PORTFILE || DEFAULT_PORTCACHE;
}

function _recvLine(sock, timeoutMs = 300000) {
  return new Promise((resolve, reject) => {
    let buf = Buffer.alloc(0);
    const timer = setTimeout(() => {
      sock.destroy();
      reject(new Error('bridge recv timeout'));
    }, timeoutMs);

    const onData = (chunk) => {
      buf = Buffer.concat([buf, chunk]);
      const idx = buf.indexOf('\n');
      if (idx >= 0) {
        clearTimeout(timer);
        sock.removeListener('data', onData);
        const line = buf.slice(0, idx);
        // keep rest? but for our protocol one response per call
        resolve(line.toString('utf8'));
      }
    };
    sock.on('data', onData);
    sock.once('error', (e) => { clearTimeout(timer); reject(e); });
    sock.once('close', () => { clearTimeout(timer); });
  });
}

async function probe(port, t = 2500) {
  return new Promise((resolve) => {
    const sock = net.connect({ port, host: '127.0.0.1', timeout: t }, () => {
      try {
        sock.write(JSON.stringify({ code: "print('pong')", shot: false }) + '\n');
      } catch (e) {
        sock.destroy();
        return resolve(false);
      }
    });

    let responded = false;

    const done = (ok) => {
      if (responded) return;
      responded = true;
      try { sock.destroy(); } catch (_) {}
      resolve(!!ok);
    };

    sock.setTimeout(t);
    sock.once('timeout', () => done(false));
    sock.once('error', () => done(false));

    sock.once('data', (chunk) => {
      const s = chunk.toString();
      if (s.includes('pong') || s.includes('"ok"')) {
        done(true);
      } else {
        done(false);
      }
    });

    sock.once('close', () => done(false));
  });
}

// MCP support (Blender MCP addon on 9876, null-terminated JSON, for live control as requested)
async function probeMcp(t = 2500) {
  return new Promise((resolve) => {
    const sock = net.connect({ port: MCP_PORT, host: '127.0.0.1', timeout: t }, () => {
      const req = JSON.stringify({ type: "execute", code: "print('pong')", strict_json: false }) + '\0';
      try { sock.write(req); } catch (e) { sock.destroy(); return resolve(false); }
    });
    let responded = false;
    const done = (ok) => {
      if (responded) return;
      responded = true;
      try { sock.destroy(); } catch (_) {}
      resolve(!!ok);
    };
    sock.setTimeout(t);
    sock.once('timeout', () => done(false));
    sock.once('error', () => done(false));
    let buf = Buffer.alloc(0);
    sock.on('data', (chunk) => {
      buf = Buffer.concat([buf, chunk]);
      if (buf.indexOf(0) >= 0) {
        const dataStr = buf.toString('utf8', 0, buf.indexOf(0));
        try {
          const resp = JSON.parse(dataStr);
          const hasPong = (resp.stdout && resp.stdout.includes('pong')) || resp.status === 'ok';
          done(!!hasPong);
        } catch (e) {
          done(false);
        }
      }
    });
    sock.once('close', () => done(false));
  });
}

function _recvUntilNull(sock) {
  return new Promise((resolve, reject) => {
    let buf = Buffer.alloc(0);
    const onData = (chunk) => {
      buf = Buffer.concat([buf, chunk]);
      if (buf.indexOf(0) >= 0) {
        sock.removeListener('data', onData);
        const data = buf.slice(0, buf.indexOf(0));
        resolve(data);
      }
    };
    sock.on('data', onData);
    sock.once('error', (e) => { sock.removeListener('data', onData); reject(e); });
    sock.once('close', () => { sock.removeListener('data', onData); resolve(buf); });
  });
}

async function discoverPort() {
  if (isMcpMode()) {
    const ok = await probeMcp().catch(() => false);
    if (ok) {
      console.log('[blender_bridge] MCP mode active on port 9876');
      return MCP_PORT;
    }
    return null;
  }

  const cacheFile = getPortCache();
  let cached = null;
  try {
    const v = fs.readFileSync(cacheFile, 'utf8').trim();
    cached = parseInt(v, 10);
  } catch (_) {}

  const order = [];
  if (cached && PORTS.includes(cached)) order.push(cached);
  for (const p of PORTS) if (!order.includes(p)) order.push(p);

  for (const p of order) {
    const ok = await probe(p).catch(() => false);
    if (ok) {
      try {
        fs.mkdirSync(path.dirname(cacheFile), { recursive: true });
        fs.writeFileSync(cacheFile, String(p));
      } catch (_) {}
      return p;
    }
  }
  return null;
}

async function send(payload, timeoutMs = 300000) {
  const port = await discoverPort();
  if (!port) {
    throw new Error('[blender_bridge] no live bridge. Run claude_bridge.py (or MCP server on 9876) inside Blender GUI then retry.');
  }

  if (isMcpMode()) {
    // MCP protocol: JSON + \0 , receive until \0
    const code = payload.code || '';
    let fullCode = code;
    if (payload.shot) {
      fullCode += `
import bpy, os
bpy.context.scene.render.filepath = r'${SHOT}'
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.ops.render.opengl(write_still=True)
print('[shot] saved')
`;
    }
    const req = JSON.stringify({ type: "execute", code: fullCode, strict_json: false }) + '\0';
    return new Promise((resolve, reject) => {
      const sock = net.connect({ port: MCP_PORT, host: '127.0.0.1' }, () => {
        sock.write(req);
      });
      sock.setTimeout(timeoutMs);
      let buf = Buffer.alloc(0);
      sock.on('data', (chunk) => {
        buf = Buffer.concat([buf, chunk]);
        if (buf.indexOf(0) >= 0) {
          const dataStr = buf.toString('utf8', 0, buf.indexOf(0));
          sock.destroy();
          try {
            const resp = JSON.parse(dataStr);
            let out = '';
            if (resp.stdout) out += resp.stdout;
            if (resp.stderr) out += '\n' + resp.stderr;
            if (resp.message) out += '\n' + resp.message;
            if (resp.result !== undefined && resp.result !== null) out += '\n' + JSON.stringify(resp.result);
            const ok = resp.status === 'ok';
            const result = { ok, out };
            if (payload.shot && fs.existsSync(SHOT)) {
              result.shot = fs.readFileSync(SHOT).toString('base64');
            }
            resolve(result);
          } catch (e) {
            reject(e);
          }
        }
      });
      sock.once('error', reject);
      sock.once('close', () => {});
    });
  }

  // socket mode (default, 9877+ newline JSON)
  return new Promise((resolve, reject) => {
    const sock = net.connect({ port, host: '127.0.0.1' }, () => {
      try {
        sock.write(JSON.stringify(payload) + '\n');
      } catch (e) {
        sock.destroy();
        reject(e);
      }
    });

    sock.setTimeout(timeoutMs);

    let settled = false;
    const finish = (r, err) => {
      if (settled) return;
      settled = true;
      try { sock.destroy(); } catch (_) {}
      if (err) reject(err); else resolve(r);
    };

    sock.once('timeout', () => finish(null, new Error('bridge socket timeout')));
    sock.once('error', (e) => finish(null, e));

    (async () => {
      try {
        const line = await _recvLine(sock, timeoutMs);
        if (!line || !line.trim()) {
          return finish(null, new Error('bridge returned empty'));
        }
        const first = line.split('\n')[0];
        const obj = JSON.parse(first);
        finish(obj);
      } catch (e) {
        finish(null, e);
      }
    })();
  });
}

async function execCode(code, wantShot = false) {
  if (typeof code !== 'string' || !code.trim()) {
    throw new Error('execCode: code must be non-empty string');
  }
  const payload = { code, shot: !!wantShot };
  const r = await send(payload);
  // Convenience: if caller wants the decoded shot saved, they can do it from r.shot
  return {
    ok: !!r.ok,
    out: r.out || '',
    shot: (r.shot && !String(r.shot).startsWith('SHOT_ERR')) ? r.shot : null,
    shotError: (r.shot && String(r.shot).startsWith('SHOT_ERR')) ? r.shot : null,
    raw: r
  };
}

// Also expose a tiny helper to request only a fresh viewport shot (no code)
async function snapshot() {
  const r = await send({ code: 'pass', shot: true });
  return {
    ok: !!r.ok,
    shot: (r.shot && !String(r.shot).startsWith('SHOT_ERR')) ? r.shot : null,
    out: r.out || ''
  };
}

module.exports = {
  PORTS,
  discoverPort,
  probe,
  send,
  execCode,
  snapshot,
  getPortCache
};
