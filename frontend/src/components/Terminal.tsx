import { useEffect, useRef, useState } from 'react'
import { Terminal as XTerm } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'

interface Props {
  wsUrl: string
  onClose: () => void
}

const QUICK_CMDS_LINUX: Record<string, { label: string; cmd: string }[]> = {
  System: [
    { label: 'OS Info', cmd: 'cat /etc/os-release' },
    { label: 'Uptime', cmd: 'uptime' },
    { label: 'Disk', cmd: 'df -h' },
    { label: 'Memory', cmd: 'free -h' },
    { label: 'CPU top', cmd: 'top -bn1 | head -25' },
    { label: 'Processes', cmd: 'ps aux --sort=-%cpu | head -20' },
    { label: 'Who logged in', cmd: 'last | head -10' },
  ],
  Network: [
    { label: 'IP addresses', cmd: 'ip addr show' },
    { label: 'Open ports', cmd: 'ss -tlnp' },
    { label: 'Public IP', cmd: 'curl -s ifconfig.me' },
    { label: 'DNS', cmd: 'cat /etc/resolv.conf' },
    { label: 'Routes', cmd: 'ip route' },
  ],
  Services: [
    { label: 'Running services', cmd: 'systemctl list-units --type=service --state=running --no-pager' },
    { label: 'Failed services', cmd: 'systemctl --failed --no-pager' },
    { label: 'Recent logs', cmd: 'journalctl -n 50 --no-pager' },
  ],
  PostgreSQL: [
    { label: 'Status', cmd: 'sudo systemctl status postgresql' },
    { label: 'List databases', cmd: "sudo -u postgres psql -c '\\l'" },
    { label: 'Connections', cmd: "sudo -u postgres psql -c 'SELECT pid,usename,datname,state FROM pg_stat_activity;'" },
    { label: 'Start', cmd: 'sudo systemctl start postgresql' },
    { label: 'Restart', cmd: 'sudo systemctl restart postgresql' },
    { label: 'Config path', cmd: 'sudo -u postgres psql -c "SHOW config_file;"' },
  ],
  MySQL: [
    { label: 'Status', cmd: 'sudo systemctl status mysql' },
    { label: 'List databases', cmd: "sudo mysql -e 'SHOW DATABASES;'" },
    { label: 'Processes', cmd: "sudo mysql -e 'SHOW PROCESSLIST;'" },
    { label: 'Start', cmd: 'sudo systemctl start mysql' },
    { label: 'Restart', cmd: 'sudo systemctl restart mysql' },
  ],
  MongoDB: [
    { label: 'Status', cmd: 'sudo systemctl status mongod' },
    { label: 'List databases', cmd: "mongosh --quiet --eval 'db.adminCommand({listDatabases:1}).databases.forEach(d=>print(d.name))'" },
    { label: 'Start', cmd: 'sudo systemctl start mongod' },
    { label: 'Restart', cmd: 'sudo systemctl restart mongod' },
  ],
  Files: [
    { label: 'Current dir', cmd: 'ls -la' },
    { label: 'Disk usage top', cmd: 'du -sh /* 2>/dev/null | sort -rh | head -15' },
    { label: 'Find large files', cmd: 'find / -size +100M -type f 2>/dev/null | head -15' },
    { label: 'Crontab', cmd: 'crontab -l 2>/dev/null' },
  ],
}

const QUICK_CMDS_WINDOWS: Record<string, { label: string; cmd: string }[]> = {
  System: [
    { label: 'OS Info', cmd: 'systeminfo | findstr /B /C:"OS"' },
    { label: 'Uptime', cmd: 'powershell -Command "(Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime | Select-Object Days,Hours,Minutes"' },
    { label: 'Disk', cmd: 'powershell -Command "Get-PSDrive -PSProvider FileSystem | Format-Table -AutoSize"' },
    { label: 'Memory', cmd: 'powershell -Command "$o=gcim Win32_OperatingSystem; Write-Output (($o.FreePhysicalMemory/1MB).ToString(\'F1\')+\'GB free of \'+($o.TotalVisibleMemorySize/1MB).ToString(\'F1\')+\'GB\')"' },
    { label: 'CPU top', cmd: 'powershell -Command "Get-Process | Sort-Object CPU -Desc | Select-Object -First 15 Name,CPU | Format-Table -AutoSize"' },
    { label: 'Processes', cmd: 'tasklist /FI "STATUS eq RUNNING"' },
    { label: 'Who logged in', cmd: 'query user' },
  ],
  Network: [
    { label: 'IP addresses', cmd: 'ipconfig' },
    { label: 'Open ports', cmd: 'netstat -an | findstr LISTENING' },
    { label: 'Public IP', cmd: 'powershell -Command "(Invoke-WebRequest -Uri ifconfig.me -UseBasicParsing).Content"' },
    { label: 'DNS', cmd: 'ipconfig /all | findstr "DNS Servers"' },
    { label: 'Routes', cmd: 'route print' },
  ],
  Services: [
    { label: 'Running services', cmd: 'powershell -Command "Get-Service | Where-Object {$_.Status -eq \'Running\'} | Format-Table -AutoSize"' },
    { label: 'Stopped services', cmd: 'powershell -Command "Get-Service | Where-Object {$_.Status -eq \'Stopped\'} | Format-Table -AutoSize"' },
    { label: 'Event log', cmd: 'powershell -Command "Get-EventLog -LogName System -Newest 20 | Format-List TimeGenerated,EntryType,Message"' },
  ],
  PostgreSQL: [
    { label: 'Status', cmd: 'sc query postgresql-x64-17' },
    { label: 'List databases', cmd: 'psql -U postgres -c "\\l"' },
    { label: 'Connections', cmd: 'psql -U postgres -c "SELECT pid,usename,datname,state FROM pg_stat_activity;"' },
    { label: 'Start', cmd: 'net start postgresql-x64-17' },
    { label: 'Restart', cmd: 'net stop postgresql-x64-17 & net start postgresql-x64-17' },
  ],
  MySQL: [
    { label: 'Status', cmd: 'sc query MySQL80' },
    { label: 'List databases', cmd: 'mysql -u root -e "SHOW DATABASES;"' },
    { label: 'Processes', cmd: 'mysql -u root -e "SHOW PROCESSLIST;"' },
    { label: 'Start', cmd: 'net start MySQL80' },
    { label: 'Restart', cmd: 'net stop MySQL80 & net start MySQL80' },
  ],
  MongoDB: [
    { label: 'Status', cmd: 'sc query MongoDB' },
    { label: 'List databases', cmd: 'mongosh --quiet --eval "db.adminCommand({listDatabases:1}).databases.forEach(d=>print(d.name))"' },
    { label: 'Start', cmd: 'net start MongoDB' },
    { label: 'Restart', cmd: 'net stop MongoDB & net start MongoDB' },
  ],
  Files: [
    { label: 'Current dir', cmd: 'dir' },
    { label: 'Disk usage', cmd: 'powershell -Command "Get-ChildItem C:\\ | Sort-Object Length -Desc | Select-Object -First 15 Name | Format-Table"' },
    { label: 'Find large files', cmd: 'powershell -Command "Get-ChildItem C:\\ -Recurse -ErrorAction SilentlyContinue | Sort-Object Length -Desc | Select-Object -First 15 FullName | Format-Table"' },
    { label: 'Scheduled tasks', cmd: 'schtasks /query /fo TABLE /nh' },
  ],
}

export default function Terminal({ wsUrl, onClose: _onClose }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const termRef = useRef<XTerm | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const fitRef = useRef<FitAddon | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')
  const [activeGroup, setActiveGroup] = useState('System')
  const [isWindows, setIsWindows] = useState<boolean | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const term = new XTerm({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: 'monospace',
      theme: { background: '#0d1117', foreground: '#c9d1d9' },
      scrollback: 5000,
    })
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(containerRef.current)
    fit.fit()
    termRef.current = term
    fitRef.current = fit

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      const { cols, rows } = term
      ws.send(JSON.stringify({ type: 'resize', cols, rows }))
    }
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data as string) as { type: string; data: string }
        if (msg.type === 'os') {
          setIsWindows(msg.data === 'windows')
        } else if (msg.type === 'output') {
          term.write(msg.data)
        } else if (msg.type === 'error') {
          term.write(`\r\n\x1b[31mError: ${msg.data}\x1b[0m\r\n`)
          setError(msg.data)
        }
      } catch { /* ignore parse errors */ }
    }
    ws.onclose = () => {
      setConnected(false)
      term.write('\r\n\x1b[33m[Connection closed]\x1b[0m\r\n')
    }
    ws.onerror = () => setError('WebSocket connection failed')

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'input', data }))
    })

    const ro = new ResizeObserver(() => {
      try { fit.fit() } catch { /* ignore */ }
      if (ws.readyState === WebSocket.OPEN) {
        const { cols, rows } = term
        ws.send(JSON.stringify({ type: 'resize', cols, rows }))
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      ws.close()
      term.dispose()
    }
  }, [wsUrl])

  const quickCmds = isWindows ? QUICK_CMDS_WINDOWS : QUICK_CMDS_LINUX

  const copyCmd = (cmd: string) => {
    navigator.clipboard.writeText(cmd).then(() => {
      setCopied(cmd)
      setTimeout(() => setCopied(''), 1500)
    }).catch(() => {})
  }

  const runCmd = (cmd: string) => {
    const ws = wsRef.current
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', data: cmd + '\n' }))
    }
  }

  return (
    <div style={{ display: 'flex', height: '100%', gap: 0 }}>
      {/* Quick commands sidebar */}
      <div style={{ width: 220, flexShrink: 0, borderRight: '1px solid var(--border)', overflowY: 'auto', background: 'var(--surface)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--border)', fontSize: 11, fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Quick Commands</span>
          {isWindows !== null && (
            <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--muted)', textTransform: 'none', letterSpacing: 0 }}>
              {isWindows ? 'Windows' : 'Linux'}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>
          {Object.keys(quickCmds).map(g => (
            <button key={g} onClick={() => setActiveGroup(g)}
              style={{ fontSize: 10, padding: '2px 6px', borderRadius: 3, border: '1px solid var(--border)', background: activeGroup === g ? 'var(--green)' : 'transparent', color: activeGroup === g ? '#000' : 'var(--muted)', cursor: 'pointer' }}>
              {g}
            </button>
          ))}
        </div>
        <div style={{ overflowY: 'auto', flex: 1 }}>
          {(quickCmds[activeGroup] ?? []).map(({ label, cmd }) => (
            <div key={cmd} style={{ padding: '6px 10px', borderBottom: '1px solid var(--border)', fontSize: 12 }}>
              <div style={{ fontWeight: 500, marginBottom: 3 }}>{label}</div>
              <code style={{ fontSize: 10, color: 'var(--muted)', display: 'block', wordBreak: 'break-all', marginBottom: 4 }}>{cmd}</code>
              <div style={{ display: 'flex', gap: 4 }}>
                <button onClick={() => copyCmd(cmd)}
                  style={{ fontSize: 10, padding: '2px 6px', borderRadius: 3, border: '1px solid var(--border)', background: copied === cmd ? 'var(--green)' : 'transparent', color: copied === cmd ? '#000' : 'var(--muted)', cursor: 'pointer' }}>
                  {copied === cmd ? 'Copied!' : 'Copy'}
                </button>
                <button onClick={() => runCmd(cmd)} disabled={!connected}
                  style={{ fontSize: 10, padding: '2px 6px', borderRadius: 3, border: '1px solid var(--border)', background: 'transparent', color: connected ? 'var(--muted)' : 'var(--border)', cursor: connected ? 'pointer' : 'not-allowed' }}>
                  Run
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Terminal area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', padding: '6px 12px', borderBottom: '1px solid var(--border)', background: 'var(--surface)', gap: 8 }}>
          <span style={{ fontSize: 12, color: connected ? 'var(--green)' : 'var(--muted)' }}>
            {connected ? '● Connected' : '○ Disconnected'}
          </span>
          {error && <span style={{ fontSize: 11, color: 'var(--red)' }}>{error}</span>}
        </div>
        <div ref={containerRef} style={{ flex: 1, background: '#0d1117', overflow: 'hidden' }} />
      </div>
    </div>
  )
}
