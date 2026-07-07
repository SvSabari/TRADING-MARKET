import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, API } from "@/lib/api";
import { fmtBytes, fmtDateTime, fmtInt, fmtNum } from "@/lib/format";
import Panel from "@/components/Panel";
import StatTile from "@/components/StatTile";
import { Download, Eye, Play, Stop } from "@phosphor-icons/react";

export default function ParquetData() {
  const [stats, setStats] = useState(null);
  const [files, setFiles] = useState([]);
  const [preview, setPreview] = useState(null);

  const load = async () => {
    const [a, b] = await Promise.all([api.get("/parquet/status"), api.get("/parquet/files")]);
    setStats(a.data); setFiles(b.data.files);
  };
  useEffect(() => {
    load();
    const i = setInterval(load, 4000);
    return () => clearInterval(i);
  }, []);

  const toggle = async (start) => {
    await api.post(start ? "/parquet/start" : "/parquet/stop");
    toast.success(start ? "Capture started" : "Capture stopped");
    load();
  };

  const doPreview = async (f) => {
    const { data } = await api.get(`/parquet/preview?path=${encodeURIComponent(f.path)}&limit=200`);
    setPreview({ ...f, rows: data.rows });
  };

  const downloadFile = async (f) => {
    try {
      const response = await api.get(`/parquet/download?path=${encodeURIComponent(f.path)}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', f.filename || `${f.symbol}.parquet`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
    } catch (e) {
      toast.error("Failed to download file");
    }
  };

  const totalRows = files.reduce((a, f) => a + (f.row_count || 0), 0);
  const totalBytes = files.reduce((a, f) => a + (f.size_bytes || 0), 0);

  return (
    <div className="space-y-4" data-testid="parquet-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 style={{ fontFamily: "Chivo", fontWeight: 900, fontSize: 28, letterSpacing: "-0.02em" }}>Parquet capture.</h1>
          <p className="dim text-sm mt-1">5-second OHLCV buckets per Nifty 50 symbol, written to a date-partitioned folder.</p>
        </div>
        <div className="flex items-center gap-2">
          {stats?.running ? (
            <button className="btn btn-danger" onClick={() => toggle(false)} data-testid="parquet-stop-btn"><Stop size={14} weight="bold" /> Stop</button>
          ) : (
            <button className="btn btn-primary" onClick={() => toggle(true)} data-testid="parquet-start-btn"><Play size={14} weight="bold" /> Start</button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-[#222]">
        <StatTile label="Status" value={stats?.running ? "RUNNING" : "STOPPED"} accent={stats?.running ? "buy" : "sell"} testid="parquet-status" big />
        <StatTile label="Rows written" value={fmtInt(stats?.rows_written || 0)} testid="parquet-rows-total" />
        <StatTile label="Files on disk" value={fmtInt(files.length)} testid="parquet-files-count" />
        <StatTile label="Total size" value={fmtBytes(totalBytes)} testid="parquet-total-size" />
      </div>

      {preview && (
        <Panel title={`Preview · ${preview.symbol}`} kicker={`${preview.rows.length} rows`} right={
          <button className="btn btn-ghost" onClick={() => setPreview(null)} data-testid="parquet-preview-close">Close</button>
        }>
          <div className="overflow-x-auto max-h-[360px]">
          <table className="w-full text-xs">
            <thead><tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
              <th className="text-left py-2 px-4">ts</th>
              <th className="text-right py-2 px-4">open</th>
              <th className="text-right py-2 px-4">high</th>
              <th className="text-right py-2 px-4">low</th>
              <th className="text-right py-2 px-4">close</th>
              <th className="text-right py-2 px-4">volume</th>
              <th className="text-right py-2 px-4">cum_vol</th>
            </tr></thead>
            <tbody className="cell-divider">
              {preview.rows.slice().reverse().map((r) => (
                <tr key={`${r.ts}-${r.symbol}`}>
                  <td className="py-2 px-4 mono dim">{fmtDateTime(r.ts)}</td>
                  <td className="py-2 px-4 text-right num">{fmtNum(r.open)}</td>
                  <td className="py-2 px-4 text-right num buy">{fmtNum(r.high)}</td>
                  <td className="py-2 px-4 text-right num sell">{fmtNum(r.low)}</td>
                  <td className="py-2 px-4 text-right num">{fmtNum(r.close)}</td>
                  <td className="py-2 px-4 text-right num">{fmtInt(r.volume)}</td>
                  <td className="py-2 px-4 text-right num dim">{fmtInt(r.cum_volume)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </Panel>
      )}

      <Panel title="Parquet files" kicker={stats?.parquet_dir}>
        <div className="max-h-[420px] overflow-y-auto">
        <table className="w-full text-xs">
          <thead><tr className="dim text-[10px] uppercase tracking-widest border-b border-[#222]">
            <th className="text-left py-2 px-4">Date</th>
            <th className="text-left py-2 px-4">Symbol</th>
            <th className="text-right py-2 px-4">Rows</th>
            <th className="text-right py-2 px-4">Size</th>
            <th className="text-left py-2 px-4">Modified</th>
            <th className="text-right py-2 px-4">Actions</th>
          </tr></thead>
          <tbody className="cell-divider">
            {[...files].sort((a, b) => new Date(b.last_modified) - new Date(a.last_modified)).map((f) => (
              <tr key={f.path} data-testid={`parquet-row-${f.symbol}`}>
                <td className="py-2 px-4 mono dim">{f.date}</td>
                <td className="py-2 px-4 mono">{f.symbol}</td>
                <td className="py-2 px-4 text-right num">{fmtInt(f.row_count)}</td>
                <td className="py-2 px-4 text-right num dim">{fmtBytes(f.size_bytes)}</td>
                <td className="py-2 px-4 mono dim">{fmtDateTime(f.last_modified)}</td>
                <td className="py-2 px-4 text-right">
                  <button className="btn btn-ghost mr-1" onClick={() => doPreview(f)} data-testid={`parquet-preview-${f.symbol}`}>
                    <Eye size={14} weight="bold" />
                  </button>
                  <button className="btn btn-ghost" onClick={() => downloadFile(f)} data-testid={`parquet-download-${f.symbol}`}>
                    <Download size={14} weight="bold" />
                  </button>
                </td>
              </tr>
            ))}
            {files.length === 0 && <tr><td colSpan={6} className="p-8 text-center dim text-xs">No files yet. Wait ~5s for the first flush.</td></tr>}
          </tbody>
        </table>
        </div>
      </Panel>

    </div>
  );
}
