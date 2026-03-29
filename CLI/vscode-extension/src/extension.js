/**
 * AIRA VS Code Extension
 * Runs the aira-scanner CLI and surfaces findings as VS Code diagnostics.
 */

const vscode = require('vscode');
const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

const DIAGNOSTIC_COLLECTION_NAME = 'aira';
const EXTENSION_NAME = 'AIRA Scanner';

// Severity mapping
const SEVERITY_MAP = {
  HIGH:   vscode.DiagnosticSeverity.Error,
  MEDIUM: vscode.DiagnosticSeverity.Warning,
  LOW:    vscode.DiagnosticSeverity.Information,
};

// Check ID to human label
const CHECK_LABELS = {
  C01: 'Success Integrity',
  C02: 'Audit Integrity',
  C03: 'Exception Suppression',
  C04: 'Fallback Control',
  C05: 'Bypass Paths',
  C06: 'Return Contracts',
  C07: 'Logic Consistency',
  C08: 'Background Tasks',
  C09: 'Environment Safety',
  C10: 'Startup Integrity',
  C11: 'Determinism',
  C12: 'Lineage',
  C13: 'Confidence Representation',
  C14: 'Test Coverage Symmetry',
  C15: 'Idempotency Safety',
};

let diagnosticCollection;
let outputChannel;
let statusBarItem;

/**
 * Extension activation
 */
function activate(context) {
  diagnosticCollection = vscode.languages.createDiagnosticCollection(DIAGNOSTIC_COLLECTION_NAME);
  outputChannel = vscode.window.createOutputChannel(EXTENSION_NAME);
  
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBarItem.text = '$(shield) AIRA';
  statusBarItem.tooltip = 'Click to run AIRA scan on workspace';
  statusBarItem.command = 'aira.scan';
  statusBarItem.show();

  context.subscriptions.push(
    diagnosticCollection,
    outputChannel,
    statusBarItem,
    vscode.commands.registerCommand('aira.scan', () => scanTarget('workspace')),
    vscode.commands.registerCommand('aira.scanFile', () => scanTarget('file')),
  );

  outputChannel.appendLine(`${EXTENSION_NAME} v1.2.0 activated`);
  outputChannel.appendLine('Commands: AIRA: Scan Workspace | AIRA: Scan Current File');
}

/**
 * Run AIRA scan
 */
async function scanTarget(mode) {
  const config = vscode.workspace.getConfiguration('aira');
  const pythonPath = config.get('pythonPath', 'python3');
  const excludeDirs = config.get('excludeDirs', []).join(',');
  const severityThreshold = config.get('severityThreshold', 'MEDIUM');

  let targetPath;
  if (mode === 'file') {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage('AIRA: No active file to scan.');
      return;
    }
    targetPath = editor.document.uri.fsPath;
  } else {
    const folders = vscode.workspace.workspaceFolders;
    if (!folders || folders.length === 0) {
      vscode.window.showWarningMessage('AIRA: No workspace folder open.');
      return;
    }
    targetPath = folders[0].uri.fsPath;
  }

  // Write JSON output to temp file
  const tmpFile = path.join(os.tmpdir(), `aira_scan_${Date.now()}.json`);
  const excludeArg = excludeDirs ? `--exclude "${excludeDirs}"` : '';
  const cmd = `${pythonPath} -m aira.cli scan "${targetPath}" --output json --out-file "${tmpFile}" ${excludeArg}`;

  statusBarItem.text = '$(sync~spin) AIRA scanning…';
  outputChannel.appendLine(`\n[${new Date().toISOString()}] Scanning: ${targetPath}`);
  outputChannel.appendLine(`Command: ${cmd}`);

  vscode.window.withProgress({
    location: vscode.ProgressLocation.Notification,
    title: 'AIRA Scanning…',
    cancellable: false,
  }, () => new Promise((resolve) => {
    exec(cmd, { cwd: targetPath }, (error, stdout, stderr) => {
      if (stderr) outputChannel.appendLine(`STDERR: ${stderr}`);
      
      try {
        if (!fs.existsSync(tmpFile)) {
          throw new Error('AIRA scanner produced no output. Is aira-scanner installed? Run: pip install aira-scanner');
        }
        
        const raw = fs.readFileSync(tmpFile, 'utf8');
        fs.unlinkSync(tmpFile);
        const report = JSON.parse(raw);
        applyDiagnostics(report, severityThreshold);
        showSummary(report);
      } catch (e) {
        outputChannel.appendLine(`Error: ${e.message}`);
        vscode.window.showErrorMessage(`AIRA: ${e.message}`);
      }

      statusBarItem.text = '$(shield) AIRA';
      resolve();
    });
  }));
}

/**
 * Apply findings as VS Code diagnostics
 */
function applyDiagnostics(report, severityThreshold) {
  diagnosticCollection.clear();

  const findings = report?.aira_scan?.findings || [];
  const thresholdOrder = { HIGH: 0, MEDIUM: 1, LOW: 2 };
  const thresholdLevel = thresholdOrder[severityThreshold] ?? 1;

  // Group by file
  const byFile = {};
  for (const finding of findings) {
    if (thresholdOrder[finding.severity] > thresholdLevel) continue;
    if (!byFile[finding.file]) byFile[finding.file] = [];
    byFile[finding.file].push(finding);
  }

  for (const [filePath, filefindings] of Object.entries(byFile)) {
    const uri = vscode.Uri.file(filePath);
    const diagnostics = filefindings.map(f => {
      const line = Math.max(0, (f.line || 1) - 1);
      const range = new vscode.Range(line, 0, line, 999);
      const checkLabel = CHECK_LABELS[f.check_id] || f.check_id;
      const msg = `[AIRA ${f.check_id} · ${checkLabel}] ${f.description}`;
      const diag = new vscode.Diagnostic(range, msg, SEVERITY_MAP[f.severity] ?? vscode.DiagnosticSeverity.Warning);
      diag.source = 'AIRA';
      diag.code = f.check_id;
      return diag;
    });
    diagnosticCollection.set(uri, diagnostics);
  }

  outputChannel.appendLine(`Applied ${findings.length} findings across ${Object.keys(byFile).length} files`);
}

/**
 * Show summary notification
 */
function showSummary(report) {
  const summary = report?.aira_scan?.summary;
  if (!summary) return;

  const high = summary.by_severity?.HIGH || 0;
  const total = summary.findings_total || 0;
  const files = summary.files_scanned || 0;

  outputChannel.appendLine(`Summary: ${files} files, ${total} findings (${high} HIGH)`);

  if (high > 0) {
    vscode.window.showErrorMessage(
      `AIRA: ${high} HIGH severity finding(s) in ${files} files. See Problems panel.`,
      'Open Problems'
    ).then(action => {
      if (action === 'Open Problems') {
        vscode.commands.executeCommand('workbench.actions.view.problems');
      }
    });
  } else if (total > 0) {
    vscode.window.showWarningMessage(`AIRA: ${total} finding(s) in ${files} files (no HIGH severity). See Problems panel.`);
  } else {
    vscode.window.showInformationMessage(`AIRA: ✓ All automated checks passed across ${files} files.`);
  }
}

function deactivate() {
  diagnosticCollection?.clear();
  diagnosticCollection?.dispose();
}

module.exports = { activate, deactivate };
