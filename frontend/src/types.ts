export type AiProvider = "none" | "ollama" | "openai" | "gemini";

export interface RepositoryMetadata {
  full_name: string;
  description: string | null;
  default_branch: string;
  stars: number;
  forks: number;
  open_issues: number;
  license: string | null;
  size_kb: number;
  html_url: string;
  languages: Record<string, number>;
  readme: string;
  files: string[];
  files_truncated: boolean;
  github_rate_limit_remaining: number | null;
}

export interface SecurityFinding {
  title: string;
  severity: "HIGH" | "MEDIUM" | "LOW" | "INFO";
  confidence: "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
  path: string;
  line: number | null;
  evidence: string;
  remediation: string;
  source: "Bandit" | "OSV";
}

export interface AnalysisReport {
  repository: RepositoryMetadata;
  findings: SecurityFinding[];
  dependency_summary: {
    scanned: number;
    unsupported: number;
    vulnerabilities: number;
    notes: string[];
  };
  readme_quality: {
    score: number;
    checks: { name: string; passed: boolean; note: string }[];
  };
  ai_summary: {
    provider: string;
    model: string;
    summary: string;
    architecture: string;
    caveat: string;
  } | null;
  ai_status: string;
  scanner_notes: string[];
  analyzed_at: string;
}
