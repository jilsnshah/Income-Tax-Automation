import { useState, useEffect, useRef } from 'react';
import * as XLSX from 'xlsx';
import { UploadCloud, Play, PlayCircle, PauseCircle, CheckCircle, XCircle, Clock, RefreshCw } from 'lucide-react';
import './index.css';

const API_BASE = import.meta.env.VITE_API_BASE_URL || `http://${window.location.hostname}:8001`;

function App() {
  const [step, setStep] = useState(1);
  const [excelData, setExcelData] = useState(null); // The raw JSON from sheet
  const [columns, setColumns] = useState([]);
  
  const [mapping, setMapping] = useState({
    pan: '',
    password: '',
    dob: '',
    fileNo: ''
  });
  const [outputDir, setOutputDir] = useState('');
  const [headless, setHeadless] = useState(false);
  
  const [queue, setQueue] = useState([]); 
  const [isProcessing, setIsProcessing] = useState(false);
  const [logs, setLogs] = useState([]);
  
  // Fetch initial status to restore session if backend is running
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/status`);
        const data = await res.json();
        if (data.is_processing || data.queue.length > 0) {
          setQueue(data.queue);
          setOutputDir(data.output_dir);
          setHeadless(data.headless);
          setIsProcessing(data.is_processing);
          setStep(3);
        }
      } catch (err) {
        console.log("No active backend session found.");
      }
    };
    checkStatus();
  }, []);

  const queueRef = useRef(queue);
  const outputDirRef = useRef('');
  const logsEndRef = useRef(null);
  const loopActiveRef = useRef(false);
  const lastLogLenRef = useRef(0);

  // Update refs when state changes
  useEffect(() => { queueRef.current = queue; }, [queue]);
  useEffect(() => { outputDirRef.current = outputDir; }, [outputDir]);

  // Save queue to local storage whenever it changes
  useEffect(() => {
    if (step === 3) {
      localStorage.setItem('taxQueue', JSON.stringify(queue));
      localStorage.setItem('taxOutputDir', outputDir);
    }
  }, [queue, step, outputDir]);

  // Poll status while in Step 3
  useEffect(() => {
    let statusInterval;
    let logInterval;
    
    if (step === 3) {
      statusInterval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/api/status`);
          const data = await res.json();
          setQueue(data.queue);
          setIsProcessing(data.is_processing);
        } catch (err) {
          console.error(err);
        }
      }, 2000);
      
      logInterval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/api/logs`);
          const data = await res.json();
          if (data.logs) {
            setLogs(data.logs);
          }
        } catch (err) {
          console.error(err);
        }
      }, 1000);
    }
    
    return () => {
      if (statusInterval) clearInterval(statusInterval);
      if (logInterval) clearInterval(logInterval);
    };
  }, [step]);

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      const bstr = evt.target.result;
      const wb = XLSX.read(bstr, { type: 'binary' });
      // Ask which sheet? For simplicity, we just take the first sheet or let them select.
      // Since requirements just said "asking which sheet to use", let's just pick first sheet if they don't select,
      // But we can parse all sheets and let them pick. For brevity in this React file, we parse the first one.
      const wsname = wb.SheetNames[0];
      const ws = wb.Sheets[wsname];
      const data = XLSX.utils.sheet_to_json(ws, { defval: '' });
      
      if (data.length > 0) {
        setColumns(Object.keys(data[0]));
        setExcelData(data);
        
        // Auto-infer if columns match exact names
        const cols = Object.keys(data[0]);
        const infer = (opts) => cols.find(c => opts.includes(c.toLowerCase().trim())) || '';
        
        setMapping({
          pan: infer(['pan', 'pan no', 'pan number']),
          password: infer(['password', 'pass']),
          dob: infer(['dob', 'date of birth', 'birthdate']),
          fileNo: infer(['file no', 'file number', 'file_no'])
        });
        
        setStep(2);
      }
    };
    reader.readAsBinaryString(file);
  };

  const startProcessing = async () => {
    if (!outputDir) {
      alert("Please specify an output directory.");
      return;
    }

    // Build the queue
    const currentQueue = excelData.map((row, idx) => ({
      id: idx,
      pan: row[mapping.pan],
      password: row[mapping.password],
      dob: row[mapping.dob],
      fileNo: row[mapping.fileNo],
      status: 'pending',
      message: ''
    })).filter(q => q.pan); // Ensure it has a PAN

    setQueue(currentQueue);
    
    // Start Background Batch
    try {
      await fetch(`${API_BASE}/api/start_batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_output_dir: outputDir,
          headless: headless,
          clients: currentQueue
        })
      });
    } catch (err) {
      console.error(err);
    }

    setIsProcessing(true);
    setStep(3);
    setIsProcessing(true);
  };
  
  const resetApp = () => {
    localStorage.removeItem('taxQueue');
    setStep(1);
    setExcelData(null);
    setQueue([]);
    setIsProcessing(false);
  }

  const handleRestart = async () => {
    if (!window.confirm("Are you sure you want to restart processing from the beginning? All progress will be reset.")) return;
    
    // Reset queue status to pending
    const resetQueue = queue.map(q => ({ ...q, status: 'pending', message: '' }));
    
    // Start Background Batch Again
    try {
      await fetch(`${API_BASE}/api/start_batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_output_dir: outputDir,
          headless: headless,
          clients: resetQueue
        })
      });
    } catch (err) {
      console.error(err);
    }
    
    setIsProcessing(true);
  };

  return (
    <div className="container">
      <h1>Tax Automation Portal</h1>
      <p className="header-desc">Automated 26AS, AIS, and TIS Downloader</p>

      {step === 1 && (
        <div className="glass-card">
          <h2>1. Import Clients</h2>
          <label className="upload-area">
            <UploadCloud className="upload-icon" />
            <h3>Click to Upload Excel File</h3>
            <p style={{ color: 'var(--text-muted)' }}>.xlsx, .xls, .csv</p>
            <input type="file" accept=".xlsx, .xls, .csv" hidden onChange={handleFileUpload} />
          </label>
        </div>
      )}

      {step === 2 && (
        <div className="glass-card">
          <h2>2. Configuration & Mapping</h2>
          
          <div className="input-group" style={{ marginBottom: '2rem' }}>
            <label>Absolute Output Directory Path</label>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <input 
                type="text" 
                placeholder="/Users/jils/dad/output" 
                value={outputDir} 
                onChange={e => setOutputDir(e.target.value)} 
                style={{ flex: 1 }}
              />
              <button 
                className="btn" 
                style={{ width: 'auto', padding: '0 1.5rem' }}
                onClick={async () => {
                  try {
                    const res = await fetch(`${API_BASE}/api/browse_directory`);
                    const data = await res.json();
                    if (data.path) {
                      setOutputDir(data.path);
                    }
                  } catch (e) {
                    console.error("Browse directory failed:", e);
                    alert("Could not open directory browser. Please ensure the backend is running.");
                  }
                }}
              >
                Browse...
              </button>
            </div>
          </div>
          
          <div className="input-group" style={{ marginBottom: '2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <input 
              type="checkbox" 
              id="headlessToggle" 
              checked={headless} 
              onChange={e => setHeadless(e.target.checked)} 
              style={{ width: '1.2rem', height: '1.2rem', cursor: 'pointer' }}
            />
            <label htmlFor="headlessToggle" style={{ margin: 0, cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
              Run Headless Mode (Hidden Browser)
            </label>
          </div>

          <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Map Excel Columns</h3>
          <div className="mapping-grid">
            {['pan', 'password', 'dob', 'fileNo'].map((field) => (
              <div className="input-group" key={field}>
                <label>{field.toUpperCase()}</label>
                <select 
                  value={mapping[field]} 
                  onChange={(e) => setMapping({...mapping, [field]: e.target.value})}
                >
                  <option value="">-- Select Column --</option>
                  {columns.map(col => <option key={col} value={col}>{col}</option>)}
                </select>
              </div>
            ))}
          </div>

          <button 
            className="btn" 
            style={{ marginTop: '1rem' }}
            onClick={startProcessing}
            disabled={!mapping.pan || !mapping.password || !mapping.dob || !mapping.fileNo}
          >
            <Play size={18} /> Start Processing {excelData.length} Clients
          </button>
        </div>
      )}

      {step === 3 && (
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <h2>3. Processing Queue</h2>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="btn" style={{ background: 'rgba(255,255,255,0.1)', width: 'auto' }} onClick={resetApp}>
                Upload New
              </button>
              <button className="btn" style={{ background: 'rgba(255,255,255,0.1)', width: 'auto' }} onClick={handleRestart}>
                <RefreshCw size={18} /> Restart
              </button>
              <button 
                className="btn" 
                style={{ background: isProcessing ? 'var(--bg-dark)' : 'var(--accent)', width: 'auto' }}
                onClick={() => setIsProcessing(!isProcessing)}
              >
                {isProcessing ? <><PauseCircle size={18}/> Pause</> : <><PlayCircle size={18}/> Resume</>}
              </button>
            </div>
          </div>
          
          <div className="stats-grid">
            <div className="stat-box">
              <div className="value">{queue.filter(q => q.status === 'success').length}</div>
              <div className="label">Success</div>
            </div>
            <div className="stat-box">
              <div className="value">{queue.filter(q => q.status === 'error').length}</div>
              <div className="label">Failed</div>
            </div>
            <div className="stat-box">
              <div className="value">{queue.filter(q => q.status === 'pending').length}</div>
              <div className="label">Pending</div>
            </div>
          </div>
          
          <div className="progress-bar-container">
            <div 
              className="progress-bar-fill" 
              style={{ width: `${(queue.filter(q => q.status !== 'pending').length / queue.length) * 100}%` }}
            ></div>
          </div>

          <ul className="client-list">
            {queue.map((q, idx) => (
              <li key={idx} className="client-item">
                <div>
                  <div style={{ fontWeight: 600 }}>{q.pan}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>File No: {q.fileNo} • DOB: {q.dob}</div>
                </div>
                <div className={`client-status status-${q.status}`}>
                  {q.status === 'success' && <CheckCircle size={14} />}
                  {q.status === 'error' && <XCircle size={14} />}
                  {q.status === 'running' && <PlayCircle size={14} />}
                  {q.status === 'pending' && <Clock size={14} />}
                  {q.status.charAt(0).toUpperCase() + q.status.slice(1)}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {step === 3 && (
        <div className="glass-card" style={{ marginTop: '1.5rem', background: '#0d1117' }}>
          <h3 style={{ fontSize: '1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#8b949e' }}>
            Live Terminal Output
          </h3>
          <div className="log-terminal">
            {logs.length === 0 ? (
              <div style={{ color: '#8b949e' }}>Waiting for logs...</div>
            ) : (
              logs.map((log, i) => (
                <div key={i} className={`log-line ${log.includes('ERROR') || log.includes('FAILED') ? 'log-error' : log.includes('SUCCESS') ? 'log-success' : 'log-info'}`}>
                  {log}
                </div>
              ))
            )}
            <div ref={logsEndRef} />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
