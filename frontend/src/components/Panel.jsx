export default function Panel({ title, kicker, right, children, className = "", testid }) {
  return (
    <div className={`panel ${className}`} data-testid={testid}>
      {(title || kicker || right) && (
        <div className="panel-h">
          <div className="flex items-center gap-2">
            {title && <span>{title}</span>}
            {kicker && <span className="kicker">· {kicker}</span>}
          </div>
          {right}
        </div>
      )}
      {children}
    </div>
  );
}
