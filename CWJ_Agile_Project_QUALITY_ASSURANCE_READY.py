"""
Agile Story Points Studio

A beginner-friendly desktop program for:
- recording user stories and Fibonacci story points
- counting only completed stories toward velocity and achieved totals
- calculating sprint velocity and average velocity
- drawing burn-down and burn-up charts
- importing/exporting CSV and JSON
- optionally importing GitHub Issues with a repository name and token

The GitHub token is used only for the current import and is not saved.
"""

import csv
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import tempfile
import sqlite3
import shutil
import base64
from datetime import date
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk


APP_TITLE = "CWJ Agile Project Studio v8 - Sprint 3 Actuals and Sprint 4"
DATA_FILE = Path.home() / "agile_story_points_data.json"
FIBONACCI_POINTS = (1, 2, 3, 5, 8, 13, 21)
STATUSES = ("Backlog", "To Do", "In Progress", "Blocked", "Completed")


@dataclass
class Story:
    title: str
    points: int
    status: str = "Backlog"
    sprint: str = "Sprint 1"
    completed_day: int = 0
    assignee: str = ""
    source: str = "Manual"
    source_id: str = ""

    @property
    def is_completed(self):
        return self.status == "Completed"


@dataclass
class Risk:
    risk_id: str
    description: str
    category: str = "Project"
    likelihood: int = 1
    impact: int = 1
    status: str = "Open"
    strategy: str = "Reduce"
    owner: str = ""
    response: str = ""
    trigger: str = ""
    contingency: str = ""
    sprint: str = "CWJ Sprint 4"

    @property
    def exposure(self):
        return int(self.likelihood) * int(self.impact)

    @property
    def active_exposure(self):
        return 0 if self.status in ("Closed", "Resolved") else self.exposure


@dataclass
class QATestCase:
    test_id: str
    title: str
    requirement_type: str = "Functional"
    test_approach: str = "Black-box"
    execution_method: str = "Manual"
    preconditions: str = ""
    steps: str = ""
    expected_result: str = ""
    actual_result: str = ""
    status: str = "Not Run"
    evidence: str = ""
    owner: str = ""

class AgileStudio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1280x780")
        self.minsize(1050, 680)
        self.configure(bg="#dcefff")

        self.stories = []
        self.sprint_days = tk.IntVar(value=15)
        self.sprint_goal = tk.IntVar(value=28)
        self.current_sprint = tk.StringVar(value="CWJ Sprint 4")
        self.status_message = tk.StringVar(value="Ready. Only Completed stories count toward achieved points.")
        self.risks = []
        self.risk_snapshots = []
        self.qa_tests = []
        self.kpis = [
            {"name": "", "measure": "", "target": "", "actual": "", "action": ""}
            for _ in range(5)
        ]
        self.retrospective = {
            "went_well": "", "did_not_go_well": "", "start_doing": "",
            "stop_doing": "", "continue_doing": "", "blockers": "",
            "decisions": "", "owners": ""
        }

        self._configure_style()
        self._build_ui()
        self.load_data(silent=True)
        self.refresh_all()

    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#dcefff")
        style.configure("Card.TFrame", background="white")
        style.configure("TLabel", background="#dcefff", font=("Times New Roman", 14))
        style.configure("Card.TLabel", background="white", font=("Times New Roman", 13))
        style.configure("Title.TLabel", background="#dcefff", foreground="#153a5b", font=("Times New Roman", 22, "bold"))
        style.configure("Metric.TLabel", background="white", foreground="#153a5b", font=("Times New Roman", 16, "bold"))
        style.configure("TButton", font=("Times New Roman", 12), padding=7)
        style.configure("Treeview", font=("Times New Roman", 12), rowheight=30)
        style.configure("Treeview.Heading", font=("Times New Roman", 12, "bold"))
        style.configure("TNotebook.Tab", font=("Times New Roman", 12, "bold"), padding=(12, 7))

    def _build_ui(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=18, pady=(14, 6))
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Completed stories only count", foreground="#8b2d2d").pack(side="right")

        controls = ttk.Frame(self, style="Card.TFrame", padding=12)
        controls.pack(fill="x", padx=18, pady=6)

        ttk.Label(controls, text="Sprint:", style="Card.TLabel").grid(row=0, column=0, padx=4)
        self.sprint_combo = ttk.Combobox(controls, textvariable=self.current_sprint, width=16,
                                         values=[f"Sprint {i}" for i in range(1, 13)] + [f"CWJ Sprint {i}" for i in range(1,5)])
        self.sprint_combo.grid(row=0, column=1, padx=4)
        self.sprint_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_all())
        self.sprint_combo.bind("<Return>", lambda _e: self.refresh_all())

        ttk.Label(controls, text="Sprint goal (points):", style="Card.TLabel").grid(row=0, column=2, padx=(18, 4))
        ttk.Spinbox(controls, from_=1, to=1000, textvariable=self.sprint_goal, width=7,
                    command=self.refresh_all).grid(row=0, column=3, padx=4)

        ttk.Label(controls, text="Sprint days:", style="Card.TLabel").grid(row=0, column=4, padx=(18, 4))
        ttk.Spinbox(controls, from_=1, to=100, textvariable=self.sprint_days, width=7,
                    command=self.refresh_all).grid(row=0, column=5, padx=4)

        ttk.Button(controls, text="Save", command=self.save_data).grid(row=0, column=6, padx=(18, 4))
        ttk.Button(controls, text="Import GitHub", command=self.import_github_dialog).grid(row=0, column=7, padx=4)
        ttk.Button(controls, text="Import Jira", command=self.import_jira_dialog).grid(row=0, column=8, padx=4)
        ttk.Button(controls, text="Import ZIP", command=self.import_zip).grid(row=0, column=9, padx=4)
        ttk.Button(controls, text="Export ZIP", command=self.export_zip).grid(row=1, column=9, padx=4, pady=(7,0))
        ttk.Button(controls, text="Import CSV/JSON", command=self.import_file).grid(row=1, column=7, padx=4, pady=(7,0))
        ttk.Button(controls, text="Export CSV", command=self.export_csv).grid(row=1, column=8, padx=4, pady=(7,0))
        ttk.Button(controls, text="Import JSON/SQLite", command=self.import_database).grid(row=2, column=7, padx=4, pady=(7,0))
        ttk.Button(controls, text="Backup All Data", command=self.backup_data).grid(row=2, column=8, padx=4, pady=(7,0))
        ttk.Button(controls, text="Load Attached Results", command=self.load_attached_results).grid(row=2, column=9, padx=4, pady=(7,0))
        ttk.Button(controls, text="Apply Sprint 3 Report", command=self.apply_sprint3_report).grid(row=3, column=9, padx=4, pady=(7,0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=18, pady=8)

        self.stories_tab = ttk.Frame(self.notebook)
        self.charts_tab = ttk.Frame(self.notebook)
        self.kpi_tab = ttk.Frame(self.notebook)
        self.retro_tab = ttk.Frame(self.notebook)
        self.report_tab = ttk.Frame(self.notebook)
        self.project_tab = ttk.Frame(self.notebook)
        self.risk_tab = ttk.Frame(self.notebook)
        self.qa_tab = ttk.Frame(self.notebook)
        self.help_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.stories_tab, text="A. User Stories")
        self.notebook.add(self.charts_tab, text="B. Burn Charts")
        self.notebook.add(self.kpi_tab, text="C. KPIs")
        self.notebook.add(self.retro_tab, text="D. Retrospective")
        self.notebook.add(self.report_tab, text="E. Sprint Report")
        self.notebook.add(self.project_tab, text="F. Project Velocity")
        self.notebook.add(self.risk_tab, text="G. Risk Management")
        self.notebook.add(self.qa_tab, text="H. Quality Assurance")
        self.notebook.add(self.help_tab, text="I. Beginner Guide")

        self._build_stories_tab()
        self._build_charts_tab()
        self._build_kpi_tab()
        self._build_retro_tab()
        self._build_report_tab()
        self._build_project_tab()
        self._build_risk_tab()
        self._build_qa_tab()
        self._build_help_tab()

        status = tk.Label(self, textvariable=self.status_message, bg="#153a5b", fg="white",
                          font=("Times New Roman", 12), anchor="w", padx=10, pady=6)
        status.pack(fill="x", side="bottom")

    def _build_stories_tab(self):
        toolbar = ttk.Frame(self.stories_tab)
        toolbar.pack(fill="x", pady=8)
        ttk.Button(toolbar, text="Add Story", command=self.add_story).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Edit Selected", command=self.edit_story).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Mark Completed", command=lambda: self.set_selected_status("Completed")).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Mark In Progress", command=lambda: self.set_selected_status("In Progress")).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete Selected", command=self.delete_story).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Load CWJ 67-Task Catalog", command=self.load_cwj_catalog).pack(side="left", padx=(18,4))

        cols = ("title", "points", "status", "sprint", "day", "assignee", "source")
        self.tree = ttk.Treeview(self.stories_tab, columns=cols, show="headings", selectmode="extended")
        headings = {
            "title": "User story / task", "points": "Points", "status": "Status",
            "sprint": "Sprint", "day": "Completed day", "assignee": "Assignee", "source": "Source"
        }
        widths = {"title": 360, "points": 70, "status": 110, "sprint": 100, "day": 110, "assignee": 130, "source": 130}
        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="center" if col != "title" else "w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.tree.bind("<Double-1>", lambda _e: self.edit_story())

        metrics = ttk.Frame(self.stories_tab, style="Card.TFrame", padding=12)
        metrics.pack(fill="x", padx=4, pady=8)
        self.metric_total = ttk.Label(metrics, style="Metric.TLabel")
        self.metric_completed = ttk.Label(metrics, style="Metric.TLabel")
        self.metric_velocity = ttk.Label(metrics, style="Metric.TLabel")
        self.metric_progress = ttk.Label(metrics, style="Metric.TLabel")
        for widget in (self.metric_total, self.metric_completed, self.metric_velocity, self.metric_progress):
            widget.pack(side="left", expand=True, padx=8)

    def _build_charts_tab(self):
        top = ttk.Frame(self.charts_tab)
        top.pack(fill="x", pady=6)
        ttk.Label(top, text="Charts use the selected sprint. Set Completed day for each finished story.").pack(side="left", padx=6)
        ttk.Button(top, text="Refresh Charts", command=self.draw_charts).pack(side="right", padx=6)
        ttk.Button(top, text="Export Charts as PostScript", command=self.export_charts).pack(side="right", padx=6)

        self.chart_canvas = tk.Canvas(self.charts_tab, bg="white", highlightthickness=1, highlightbackground="#aac6db")
        self.chart_canvas.pack(fill="both", expand=True, padx=5, pady=5)
        self.chart_canvas.bind("<Configure>", lambda _e: self.draw_charts())

    def _build_kpi_tab(self):
        intro = ttk.Label(
            self.kpi_tab,
            text="Enter up to five KPIs. A useful KPI should have a clear measure, target, actual result and next action.",
        )
        intro.pack(anchor="w", padx=8, pady=(10, 4))

        table = ttk.Frame(self.kpi_tab, style="Card.TFrame", padding=10)
        table.pack(fill="both", expand=True, padx=6, pady=6)
        headers = ["KPI name", "How it is measured", "Target", "Actual", "Action if off target", "Assessment"]
        widths = [20, 28, 12, 12, 28, 18]
        for column, heading in enumerate(headers):
            ttk.Label(table, text=heading, style="Card.TLabel", font=("Times New Roman", 12, "bold")).grid(
                row=0, column=column, padx=3, pady=4, sticky="ew"
            )
            table.columnconfigure(column, weight=2 if column in (1, 4) else 1)

        self.kpi_vars = []
        self.kpi_assessment_labels = []
        for row in range(5):
            values = self.kpis[row]
            vars_for_row = [
                tk.StringVar(value=values["name"]), tk.StringVar(value=values["measure"]),
                tk.StringVar(value=values["target"]), tk.StringVar(value=values["actual"]),
                tk.StringVar(value=values["action"]),
            ]
            self.kpi_vars.append(vars_for_row)
            for column, variable in enumerate(vars_for_row):
                entry = ttk.Entry(table, textvariable=variable, width=widths[column])
                entry.grid(row=row + 1, column=column, padx=3, pady=5, sticky="ew")
                variable.trace_add("write", lambda *_args, r=row: self.assess_kpi(r))
            label = ttk.Label(table, text="Placeholder", style="Card.TLabel")
            label.grid(row=row + 1, column=5, padx=3, pady=5, sticky="w")
            self.kpi_assessment_labels.append(label)

        buttons = ttk.Frame(self.kpi_tab)
        buttons.pack(fill="x", padx=8, pady=6)
        ttk.Button(buttons, text="Load Suggested KPIs", command=self.load_suggested_kpis).pack(side="left", padx=4)
        ttk.Button(buttons, text="Save KPI Entries", command=self.capture_kpis_and_save).pack(side="left", padx=4)
        ttk.Button(buttons, text="Refresh Assessments", command=self.assess_all_kpis).pack(side="left", padx=4)
        self.assess_all_kpis()

    def load_suggested_kpis(self):
        suggestions = [
            ("Sprint completion rate", "Completed points divided by committed points (%)", "80", "", "Reduce commitment or split oversized stories"),
            ("Sprint velocity", "Completed story points in this sprint", "", "", "Review blockers and estimation accuracy"),
            ("Carryover stories", "Count of unfinished stories moved to next sprint", "0", "", "Identify cause and assign an owner"),
            ("Defects found", "Number of confirmed defects during the sprint", "0", "", "Add testing or acceptance checks"),
            ("Team action completion", "Retrospective actions completed by due date (%)", "100", "", "Reduce actions and confirm owners"),
        ]
        for row, values in enumerate(suggestions):
            for column, value in enumerate(values):
                self.kpi_vars[row][column].set(value)
        self.assess_all_kpis()

    def capture_kpis_and_save(self):
        for row, variables in enumerate(self.kpi_vars):
            self.kpis[row] = {
                "name": variables[0].get().strip(), "measure": variables[1].get().strip(),
                "target": variables[2].get().strip(), "actual": variables[3].get().strip(),
                "action": variables[4].get().strip(),
            }
        self.save_data(silent=True)
        self.refresh_report()
        self.status_message.set("KPI entries saved.")

    def assess_kpi(self, row):
        if not hasattr(self, "kpi_vars") or row >= len(self.kpi_vars):
            return
        name, measure, target, actual, action = [v.get().strip() for v in self.kpi_vars[row]]
        missing = []
        if not name: missing.append("name")
        if not measure: missing.append("measure")
        if not target: missing.append("target")
        if not action: missing.append("action")
        if missing:
            result = "Needs: " + ", ".join(missing)
            colour = "#8b2d2d"
        elif not actual:
            result = "Measurable; actual pending"
            colour = "#8a5a00"
        else:
            result = "Measurable and actionable"
            colour = "#23633b"
        self.kpi_assessment_labels[row].config(text=result, foreground=colour)

    def assess_all_kpis(self):
        if hasattr(self, "kpi_vars"):
            for row in range(5):
                self.assess_kpi(row)

    def _build_retro_tab(self):
        ttk.Label(
            self.retro_tab,
            text="Use evidence from user stories, KPIs and charts. Finish with a small number of owned actions.",
        ).pack(anchor="w", padx=8, pady=(10, 4))
        frame = ttk.Frame(self.retro_tab, style="Card.TFrame", padding=10)
        frame.pack(fill="both", expand=True, padx=6, pady=6)
        fields = [
            ("went_well", "What went well?"), ("did_not_go_well", "What did not go well?"),
            ("start_doing", "What should we start doing?"), ("stop_doing", "What should we stop doing?"),
            ("continue_doing", "What should we continue doing?"), ("blockers", "Blockers and causes"),
            ("decisions", "Agreed improvement actions"), ("owners", "Action owners and due points"),
        ]
        self.retro_widgets = {}
        for index, (key, label) in enumerate(fields):
            row, column = divmod(index, 2)
            cell = ttk.Frame(frame, style="Card.TFrame")
            cell.grid(row=row, column=column, padx=6, pady=5, sticky="nsew")
            frame.columnconfigure(column, weight=1)
            frame.rowconfigure(row, weight=1)
            ttk.Label(cell, text=label, style="Card.TLabel", font=("Times New Roman", 12, "bold")).pack(anchor="w")
            widget = tk.Text(cell, height=5, wrap="word", font=("Times New Roman", 12), bg="#fffdf8")
            widget.pack(fill="both", expand=True)
            widget.insert("1.0", self.retrospective.get(key, ""))
            self.retro_widgets[key] = widget
        buttons = ttk.Frame(self.retro_tab)
        buttons.pack(fill="x", padx=8, pady=6)
        ttk.Button(buttons, text="Suggest Retrospective Evidence", command=self.suggest_retrospective).pack(side="left", padx=4)
        ttk.Button(buttons, text="Save Retrospective", command=self.capture_retro_and_save).pack(side="left", padx=4)

    def capture_retro_and_save(self):
        for key, widget in self.retro_widgets.items():
            self.retrospective[key] = widget.get("1.0", "end").strip()
        self.save_data(silent=True)
        self.refresh_report()
        self.status_message.set("Retrospective saved.")

    def suggest_retrospective(self):
        stories = self.filtered_stories()
        completed = [s for s in stories if s.is_completed]
        unfinished = [s for s in stories if not s.is_completed]
        completed_points = sum(s.points for s in completed)
        planned_points = sum(s.points for s in stories)
        evidence = (
            f"Evidence: {len(completed)} completed stories worth {completed_points} points; "
            f"{len(unfinished)} unfinished stories; {planned_points} planned points."
        )
        suggestions = {
            "went_well": evidence + " Record the specific practices that helped completed work reach Done.",
            "did_not_go_well": "Review unfinished and blocked stories, late scope changes, defects and missed KPI targets.",
            "start_doing": "Split large stories, confirm acceptance criteria before work starts, and review the burn chart during stand-ups.",
            "stop_doing": "Stop counting partial work as completed and avoid adding unplanned work without an explicit trade-off.",
            "continue_doing": "Continue practices supported by completed stories, stable progress and useful team communication.",
            "blockers": "List each blocker, its cause, when it appeared and how long it affected progress.",
            "decisions": "Choose one or two measurable improvements for the next sprint.",
            "owners": "Assign one owner and a review point for every agreed action.",
        }
        for key, text in suggestions.items():
            widget = self.retro_widgets[key]
            widget.delete("1.0", "end")
            widget.insert("1.0", text)

    def _build_report_tab(self):
        toolbar = ttk.Frame(self.report_tab)
        toolbar.pack(fill="x", pady=7)
        ttk.Button(toolbar, text="Generate Sprint Report", command=self.refresh_report).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Export Report TXT", command=self.export_sprint_report).pack(side="left", padx=4)
        self.report_text = tk.Text(self.report_tab, wrap="word", font=("Times New Roman", 13), bg="white", padx=16, pady=12)
        self.report_text.pack(fill="both", expand=True, padx=6, pady=6)
        self.refresh_report()

    def build_sprint_report_text(self):
        stories = self.filtered_stories()
        completed = [s for s in stories if s.is_completed]
        unfinished = [s for s in stories if not s.is_completed]
        blocked = [s for s in stories if s.status == "Blocked"]
        planned_points = sum(s.points for s in stories)
        completed_points = sum(s.points for s in completed)
        completion_rate = (completed_points / planned_points * 100) if planned_points else 0
        kpi_lines = []
        for index, kpi in enumerate(self.kpis, 1):
            if kpi.get("name"):
                kpi_lines.append(
                    f"{index}. {kpi['name']} | Measure: {kpi['measure']} | Target: {kpi['target']} | "
                    f"Actual: {kpi['actual'] or 'Pending'} | Action: {kpi['action']}"
                )
        if not kpi_lines:
            kpi_lines = ["No KPIs have been entered."]
        completed_lines = [f"- {s.title} ({s.points} points)" for s in completed] or ["- None recorded"]
        unfinished_lines = [f"- {s.title} [{s.status}] ({s.points} points)" for s in unfinished] or ["- None"]
        retro = self.retrospective
        return "\n".join([
            "SPRINT REPORT", "=" * 60,
            f"Sprint: {self.current_sprint.get()}",
            f"Sprint point goal: {self.safe_int(self.sprint_goal.get(), 0)}",
            f"Planned points in stories: {planned_points}",
            f"Completed points / velocity: {completed_points}",
            f"Point completion rate: {completion_rate:.1f}%",
            f"Completed stories: {len(completed)} of {len(stories)}",
            f"Blocked stories: {len(blocked)}",
            f"Active risks: {sum(1 for r in self.risks if r.sprint == self.current_sprint.get() and r.status not in ('Closed','Resolved'))}",
            f"Active risk exposure: {self.current_risk_exposure(self.current_sprint.get())}", "",
            "COMPLETED WORK", *completed_lines, "",
            "UNFINISHED OR CARRYOVER WORK", *unfinished_lines, "",
            "KPIs", *kpi_lines, "",
            "RISKS", *([f"- {r.risk_id}: {r.description} | exposure {r.exposure} | {r.strategy} | owner {r.owner}" for r in self.risks if r.sprint == self.current_sprint.get() and r.status not in ("Closed","Resolved")] or ["- No active risks recorded"]), "",
            "QUALITY ASSURANCE", *self.qa_report_lines(), "",
            "RETROSPECTIVE", f"Went well: {retro.get('went_well') or 'Not entered'}",
            f"Did not go well: {retro.get('did_not_go_well') or 'Not entered'}",
            f"Start: {retro.get('start_doing') or 'Not entered'}",
            f"Stop: {retro.get('stop_doing') or 'Not entered'}",
            f"Continue: {retro.get('continue_doing') or 'Not entered'}",
            f"Blockers: {retro.get('blockers') or 'Not entered'}",
            f"Actions: {retro.get('decisions') or 'Not entered'}",
            f"Owners: {retro.get('owners') or 'Not entered'}", "",
            "RULE: Only fully Completed stories count toward velocity and achievement.",
        ])

    def refresh_report(self):
        if not hasattr(self, "report_text"):
            return
        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", self.build_sprint_report_text())
        self.report_text.configure(state="disabled")

    def export_sprint_report(self):
        self.capture_kpis_and_save()
        self.capture_retro_and_save()
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text report", "*.txt")],
            initialfile=f"{self.current_sprint.get().replace(' ', '_')}_Sprint_Report.txt",
        )
        if path:
            Path(path).write_text(self.build_sprint_report_text(), encoding="utf-8")
            self.status_message.set(f"Sprint report exported to {Path(path).name}.")

    def _build_project_tab(self):
        toolbar = ttk.Frame(self.project_tab)
        toolbar.pack(fill="x", pady=7)
        ttk.Label(toolbar, text="Cross-sprint velocity and total project burn-up based on the loaded CWJ catalog.").pack(side="left", padx=6)
        ttk.Button(toolbar, text="Refresh Project Charts", command=self.draw_project_charts).pack(side="right", padx=6)
        self.project_canvas = tk.Canvas(self.project_tab, bg="white", highlightthickness=1, highlightbackground="#aac6db")
        self.project_canvas.pack(fill="both", expand=True, padx=6, pady=6)
        self.project_canvas.bind("<Configure>", lambda _e: self.draw_project_charts())

    def load_cwj_catalog(self):
        if self.stories and not messagebox.askyesno(
            APP_TITLE,
            "Load the complete 67-task CWJ catalog? Existing items with the same CWJ key will be updated; other items are kept.",
        ):
            return
        catalog = self.cwj_catalog_data()
        loaded = 0
        for row in catalog:
            source_id = f"cwj:{row[0]}"
            story = Story(
                title=f"{row[0]} - {row[1]}", points=row[2], status=row[3], sprint=row[4],
                completed_day=row[5], assignee=row[6], source="CWJ Sprint Catalog PDF", source_id=source_id,
            )
            index = next((i for i, old in enumerate(self.stories) if old.source_id == source_id), None)
            if index is None:
                self.stories.append(story)
            else:
                self.stories[index] = story
            loaded += 1
        self.current_sprint.set("CWJ Sprint 3")
        self.sprint_goal.set(28)
        self.sprint_days.set(15)
        self.save_data(silent=True)
        self.refresh_all()
        self.draw_project_charts()
        messagebox.showinfo(
            APP_TITLE,
            f"Loaded {loaded} CWJ tasks across four sprints.\n\n"
            "Sprint 1: 38/38 points completed\nSprint 2: 32/32 points completed\n"
            "Sprint 3: 0/28 points completed\nSprint 4: 0/28 points completed\n\n"
            "Total consistent scope: 126 points; completed: 70; remaining: 56.",
        )

    @staticmethod
    def cwj_catalog_data():
        # key, title, points, status, sprint, completed_day, assignee
        s1 = [
            ("CWJ-1","Project Name",1),("CWJ-2","3 Project Goals",1),("CWJ-3","Clear Objectives",1),
            ("CWJ-4","Scope",1),("CWJ-5","Stakeholders",1),("CWJ-6","Roadmap",2),
            ("CWJ-7","Strategic Thinking",1),("CWJ-8","SDG Alignment",1),("CWJ-9","SWOT Analysis",1),
            ("CWJ-10","Balanced Scorecard",2),("CWJ-11","Portfolio Management",1),("CWJ-12","Long Term Goals",1),
            ("CWJ-13","Short Term Goals",1),("CWJ-14","Stakeholder Engagement Plan",1),("CWJ-15","Deliverables",1),
            ("CWJ-16","Timeline",2),("CWJ-17","Resources",1),("CWJ-18","Communication Plan",1),
            ("CWJ-19","Risk Management",2),("CWJ-20","Project Selection Criteria",1),("CWJ-21","Cost-Benefit Analysis",1),
            ("CWJ-22","Feasibility Study",2),("CWJ-23","Functional & Non-Functional Requirements",2),
            ("CWJ-24","User Stories",2),("CWJ-25","Requirement Elicitation Methods",1),
            ("CWJ-26","Analysing and Prioritisation Requirements",1),("CWJ-27","UML",3,"Aaron Davis"),
            ("CWJ-28","Wireframe",3,"Aaron Davis"),("CWJ-29","SCRUM Setup In Jira and Confluence Page",2,"Hannah Kingston"),
        ]
        s2 = [
            ("CWJ-30","Drag and drop mechanics",3,"Brendan Atherton"),("CWJ-31","Spelling Challenge",5,"Brendan Atherton"),
            ("CWJ-32","Animations",2,"Brendan Atherton"),("CWJ-33","Sound",2,"Brendan Atherton"),
            ("CWJ-40","Write 3-5 User Stories",2,"Hannah Kingston"),("CWJ-41","Set up project repository and workflow",2,"Aaron Davis"),
            ("CWJ-42","Create Jira Backlog and Sprint Board",1,"Hannah Kingston"),
            ("CWJ-43","Break User Stories Into Development Tasks",2,"Hannah Kingston"),
            ("CWJ-44","Begin Coding Key Features",5,"Brendan Atherton"),("CWJ-45","Implement the wireframe",3,"Aaron Davis"),
            ("CWJ-46","Create database structure plan",2,"Aaron Davis"),("CWJ-47","Sprint 1 Review",1,"Brendan Atherton"),
            ("CWJ-48","Sprint 1 Retrospective",1,"Brendan Atherton"),("CWJ-49","Update Documentation",1,"Hannah Kingston"),
        ]
        s3 = [
            ("CWJ-34","Sone Mini-Game Design",3),("CWJ-35","UI Screens",3),("CWJ-36","Level Progression",3),
            ("CWJ-60","Core features",5),("CWJ-61","Functional testing",3),("CWJ-62","Big Fixes (Bug Fixes)",3),
            ("CWJ-63","Review requirements implementation",2),("CWJ-64","Improve UI/UX",3),("CWJ-65","Review risks",1),
            ("CWJ-66","Sprint 2 review",1),("CWJ-67","Sprint 2 retrospective",1),
        ]
        s4 = [
            ("CWJ-37","Final Documentation",3),("CWJ-38","Presentation",2),("CWJ-39","Refinement",3),
            ("CWJ-50","Bug fixes",2),("CWJ-51","Performance improvements",2),("CWJ-52","Complete documentation",2),
            ("CWJ-53","Final testing",3),("CWJ-54","Final review (functional & nonfunctional requirements)",2),
            ("CWJ-55","Prepare demonstration script",2),("CWJ-56","Prepare presentation slides",3),
            ("CWJ-57","Gather evidence for individual assessment",2),("CWJ-58","Sprint 3 Retrospective",1),
            ("CWJ-59","Sprint 3 Review",1),
        ]
        rows=[]
        for idx, item in enumerate(s1, 1):
            key,title,pts,*assignee=item
            rows.append((key,title,pts,"Completed","CWJ Sprint 1",min(15,max(1,(idx+1)//2)),assignee[0] if assignee else ""))
        for idx, item in enumerate(s2, 1):
            key,title,pts,*assignee=item
            rows.append((key,title,pts,"Completed","CWJ Sprint 2",min(15,idx),assignee[0] if assignee else ""))
        for item in s3:
            key,title,pts=item
            rows.append((key,title,pts,"To Do","CWJ Sprint 3",0,""))
        for item in s4:
            key,title,pts=item
            rows.append((key,title,pts,"To Do","CWJ Sprint 4",0,""))
        return rows

    def draw_project_charts(self):
        if not hasattr(self, "project_canvas"):
            return
        c=self.project_canvas
        c.delete("all")
        width=max(850,c.winfo_width()); height=max(500,c.winfo_height())
        sprint_names=["CWJ Sprint 1","CWJ Sprint 2","CWJ Sprint 3","CWJ Sprint 4"]
        committed=[]; completed=[]
        for name in sprint_names:
            items=[x for x in self.stories if x.sprint==name]
            committed.append(sum(x.points for x in items))
            completed.append(sum(x.points for x in items if x.is_completed))
        total_scope=sum(committed); cumulative=[]; running=0
        for value in completed:
            running+=value; cumulative.append(running)
        remaining=[total_scope-x for x in cumulative]
        margin=70; mid=width/2; chart_h=height-150; y0=65; y1=y0+chart_h
        max_y=max(total_scope,1)
        def x_pos(i,left,right): return left+(right-left)*i/3
        def y_pos(v): return y1-chart_h*v/max_y
        # Burn-up
        left=margin; right=mid-35
        c.create_text((left+right)/2,25,text="Project Burn-Up",font=("Times New Roman",17,"bold"),fill="#153a5b")
        c.create_line(left,y0,left,y1,width=2); c.create_line(left,y1,right,y1,width=2)
        c.create_line(left,y_pos(total_scope),right,y_pos(total_scope),fill="#777",dash=(6,4),width=2)
        pts=[]
        for i,v in enumerate(cumulative): pts += [x_pos(i,left,right),y_pos(v)]
        if len(pts)>=4: c.create_line(*pts,fill="#2f7d4f",width=3)
        for i,v in enumerate(cumulative):
            x=x_pos(i,left,right); y=y_pos(v); c.create_oval(x-4,y-4,x+4,y+4,fill="#2f7d4f"); c.create_text(x,y-14,text=str(v),font=("Times New Roman",10,"bold")); c.create_text(x,y1+18,text=f"S{i+1}",font=("Times New Roman",10))
        # Burndown
        left=mid+35; right=width-margin
        c.create_text((left+right)/2,25,text="Project Burn-Down",font=("Times New Roman",17,"bold"),fill="#153a5b")
        c.create_line(left,y0,left,y1,width=2); c.create_line(left,y1,right,y1,width=2)
        pts=[]
        for i,v in enumerate(remaining): pts += [x_pos(i,left,right),y_pos(v)]
        if len(pts)>=4: c.create_line(*pts,fill="#b54c4c",width=3)
        for i,v in enumerate(remaining):
            x=x_pos(i,left,right); y=y_pos(v); c.create_oval(x-4,y-4,x+4,y+4,fill="#b54c4c"); c.create_text(x,y-14,text=str(v),font=("Times New Roman",10,"bold")); c.create_text(x,y1+18,text=f"S{i+1}",font=("Times New Roman",10))
        for q in range(6):
            val=max_y*q/5; yy=y_pos(val)
            c.create_text(margin-10,yy,text=f"{val:.0f}",anchor="e",font=("Times New Roman",9))
            c.create_text(mid+25,yy,text=f"{val:.0f}",anchor="e",font=("Times New Roman",9))
        avg=(completed[0]+completed[1])/2 if len(completed)>=2 else 0
        c.create_text(width/2,height-42,text=f"Scope {total_scope} pts | Completed {sum(completed)} pts | Remaining {total_scope-sum(completed)} pts | Historical velocity average {avg:.1f} pts/sprint",font=("Times New Roman",13,"bold"),fill="#153a5b")

    def _build_risk_tab(self):
        # Make the complete Risk Management page vertically scrollable so the
        # chart and controls at the bottom remain readable on smaller screens.
        risk_page_canvas = tk.Canvas(
            self.risk_tab,
            bg="#dcefff",
            highlightthickness=0,
        )
        risk_page_scrollbar = ttk.Scrollbar(
            self.risk_tab,
            orient="vertical",
            command=risk_page_canvas.yview,
        )
        risk_page_canvas.configure(yscrollcommand=risk_page_scrollbar.set)

        risk_page_scrollbar.pack(side="right", fill="y")
        risk_page_canvas.pack(side="left", fill="both", expand=True)

        risk_content = ttk.Frame(risk_page_canvas)
        risk_window = risk_page_canvas.create_window(
            (0, 0), window=risk_content, anchor="nw"
        )

        def update_scroll_region(_event=None):
            risk_page_canvas.configure(scrollregion=risk_page_canvas.bbox("all"))

        def match_content_width(event):
            risk_page_canvas.itemconfigure(risk_window, width=event.width)

        def scroll_risk_page(event):
            if event.delta:
                risk_page_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4:
                risk_page_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                risk_page_canvas.yview_scroll(1, "units")

        risk_content.bind("<Configure>", update_scroll_region)
        risk_page_canvas.bind("<Configure>", match_content_width)
        risk_page_canvas.bind("<Enter>", lambda _e: risk_page_canvas.bind_all("<MouseWheel>", scroll_risk_page))
        risk_page_canvas.bind("<Leave>", lambda _e: risk_page_canvas.unbind_all("<MouseWheel>"))
        risk_page_canvas.bind("<Enter>", lambda _e: (
            risk_page_canvas.bind_all("<MouseWheel>", scroll_risk_page),
            risk_page_canvas.bind_all("<Button-4>", scroll_risk_page),
            risk_page_canvas.bind_all("<Button-5>", scroll_risk_page),
        ), add="+")
        risk_page_canvas.bind("<Leave>", lambda _e: (
            risk_page_canvas.unbind_all("<MouseWheel>"),
            risk_page_canvas.unbind_all("<Button-4>"),
            risk_page_canvas.unbind_all("<Button-5>"),
        ), add="+")

        toolbar = ttk.Frame(risk_content)
        toolbar.pack(fill="x", pady=7)
        ttk.Button(toolbar, text="Load Suggested Sprint 4 Risks", command=self.load_sprint4_risks).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Add Risk", command=self.add_risk).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Edit Selected", command=self.edit_risk).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Close Selected", command=self.close_risk).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete Selected", command=self.delete_risk).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Capture Exposure Snapshot", command=self.capture_risk_snapshot).pack(side="right", padx=4)

        table_frame = ttk.Frame(risk_content)
        table_frame.pack(fill="both", expand=True, padx=5, pady=5)

        cols = ("id","description","category","likelihood","impact","exposure","status","strategy","owner","sprint")
        self.risk_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=10, selectmode="extended")
        labels = {"id":"ID","description":"Risk","category":"Category","likelihood":"Likelihood","impact":"Impact","exposure":"Exposure","status":"Status","strategy":"Strategy","owner":"Owner","sprint":"Sprint"}
        widths = {"id":55,"description":350,"category":95,"likelihood":75,"impact":65,"exposure":75,"status":85,"strategy":85,"owner":130,"sprint":105}
        for col in cols:
            self.risk_tree.heading(col, text=labels[col])
            self.risk_tree.column(col, width=widths[col], anchor="w" if col in ("description","owner") else "center")

        tree_y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.risk_tree.yview)
        tree_x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.risk_tree.xview)
        self.risk_tree.configure(
            yscrollcommand=tree_y_scrollbar.set,
            xscrollcommand=tree_x_scrollbar.set,
        )
        self.risk_tree.grid(row=0, column=0, sticky="nsew")
        tree_y_scrollbar.grid(row=0, column=1, sticky="ns")
        tree_x_scrollbar.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.risk_tree.bind("<Double-1>", lambda _e: self.edit_risk())

        ttk.Label(
            risk_content,
            text="Risk Exposure Chart",
            font=("Times New Roman", 14, "bold"),
        ).pack(anchor="w", padx=7, pady=(10, 0))

        self.risk_canvas = tk.Canvas(
            risk_content,
            bg="white",
            height=320,
            highlightthickness=1,
            highlightbackground="#aac6db",
        )
        self.risk_canvas.pack(fill="x", padx=5, pady=(5, 18))
        self.risk_canvas.bind("<Configure>", lambda _e: self.draw_risk_chart())

    def refresh_risks(self):
        if not hasattr(self, "risk_tree"): return
        for item in self.risk_tree.get_children(): self.risk_tree.delete(item)
        for index, risk in enumerate(self.risks):
            self.risk_tree.insert("", "end", iid=str(index), values=(risk.risk_id,risk.description,risk.category,risk.likelihood,risk.impact,risk.exposure,risk.status,risk.strategy,risk.owner,risk.sprint))
        self.draw_risk_chart()

    def add_risk(self): self.risk_dialog()
    def edit_risk(self):
        selected = self.risk_tree.selection()
        if selected: self.risk_dialog(int(selected[0]))

    def risk_dialog(self, index=None):
        current = self.risks[index] if index is not None else Risk(f"R{len(self.risks)+1}", "", sprint=self.current_sprint.get())
        win = tk.Toplevel(self); win.title("Risk Item"); win.transient(self); win.grab_set(); win.configure(bg="#dcefff")
        frame = ttk.Frame(win, style="Card.TFrame", padding=14); frame.pack(padx=12, pady=12)
        specs=[("Risk ID",current.risk_id,None),("Description",current.description,None),("Category",current.category,None),("Likelihood 1-5",str(current.likelihood),[1,2,3,4,5]),("Impact 1-5",str(current.impact),[1,2,3,4,5]),("Status",current.status,["Open","Monitoring","Mitigated","Escalated","Closed","Resolved"]),("Strategy",current.strategy,["Avoid","Transfer","Reduce","Accept"]),("Owner",current.owner,None),("Response / mitigation",current.response,None),("Trigger",current.trigger,None),("Contingency",current.contingency,None),("Sprint",current.sprint,[f"CWJ Sprint {i}" for i in range(1,5)])]
        variables=[]
        for row,(label,value,choices) in enumerate(specs):
            ttk.Label(frame,text=label,style="Card.TLabel").grid(row=row,column=0,sticky="w",padx=4,pady=4)
            var=tk.StringVar(value=value); variables.append(var)
            widget=ttk.Combobox(frame,textvariable=var,values=choices,width=48) if choices else ttk.Entry(frame,textvariable=var,width=51)
            widget.grid(row=row,column=1,padx=4,pady=4)
        def save_risk():
            try: likelihood=max(1,min(5,int(variables[3].get()))); impact=max(1,min(5,int(variables[4].get())))
            except ValueError: messagebox.showerror(APP_TITLE,"Likelihood and impact must be 1 to 5.",parent=win); return
            item=Risk(variables[0].get().strip() or f"R{len(self.risks)+1}",variables[1].get().strip(),variables[2].get().strip() or "Project",likelihood,impact,variables[5].get(),variables[6].get(),variables[7].get().strip(),variables[8].get().strip(),variables[9].get().strip(),variables[10].get().strip(),variables[11].get())
            if not item.description: messagebox.showerror(APP_TITLE,"Enter a risk description.",parent=win); return
            if index is None: self.risks.append(item)
            else: self.risks[index]=item
            self.save_data(silent=True); self.refresh_all(); win.destroy()
        ttk.Button(frame,text="Save Risk",command=save_risk).grid(row=len(specs),column=0,columnspan=2,pady=10)

    def close_risk(self):
        for item in self.risk_tree.selection(): self.risks[int(item)].status="Closed"
        self.save_data(silent=True); self.refresh_all()
    def delete_risk(self):
        for index in sorted((int(x) for x in self.risk_tree.selection()), reverse=True): del self.risks[index]
        self.save_data(silent=True); self.refresh_all()
    def current_risk_exposure(self, sprint=None):
        return sum(r.active_exposure for r in self.risks if sprint is None or r.sprint == sprint)
    def capture_risk_snapshot(self):
        self.risk_snapshots.append({"time":datetime.now().isoformat(timespec="seconds"),"sprint":self.current_sprint.get(),"exposure":self.current_risk_exposure(self.current_sprint.get())})
        self.save_data(silent=True); self.refresh_all(); self.status_message.set("Risk exposure snapshot captured.")
    def draw_risk_chart(self):
        if not hasattr(self,"risk_canvas"): return
        c=self.risk_canvas; c.delete("all"); width=max(760,c.winfo_width())
        sprint=self.current_sprint.get(); active=[r for r in self.risks if r.sprint==sprint and r.status not in ("Closed","Resolved")]
        total=sum(r.active_exposure for r in active); c.create_text(15,18,text=f"{sprint}: active exposure {total} | open risks {len(active)}",anchor="w",font=("Times New Roman",15,"bold"),fill="#153a5b")
        top=sorted(active,key=lambda r:r.exposure,reverse=True)[:8]; maximum=max([r.exposure for r in top] or [1]); y=48
        for risk in top:
            bar=(width-360)*risk.exposure/maximum; colour="#b54c4c" if risk.exposure>=15 else "#d98c3f" if risk.exposure>=8 else "#5e8f68"
            c.create_text(15,y+10,text=risk.risk_id,anchor="w",font=("Times New Roman",10,"bold")); c.create_rectangle(60,y,60+bar,y+20,fill=colour,outline=colour); c.create_text(70+bar,y+10,text=f"{risk.exposure}  {risk.description[:64]}",anchor="w",font=("Times New Roman",10)); y+=29
        snapshots=[x for x in self.risk_snapshots if x.get("sprint")==sprint]
        if snapshots: c.create_text(width-15,18,text=f"Snapshots: {len(snapshots)} | latest {snapshots[-1].get('exposure',0)}",anchor="e",font=("Times New Roman",11))

    def load_sprint4_risks(self):
        suggestions=[
            Risk("R5","Final presentation evidence may be incomplete","Assessment",3,4,"Open","Reduce","Team","Capture screenshots, commits and reports throughout Sprint 4","Evidence folders remain incomplete near review","Recover evidence from Git, Jira, Confluence and exported reports","CWJ Sprint 4"),
            Risk("R6","Final testing may reveal defects too late for correction","Quality",4,5,"Open","Reduce","Team","Run regression and acceptance tests early in Sprint 4","High-severity defect appears during final review","Prioritise critical fixes and defer lower-value refinement","CWJ Sprint 4"),
            Risk("R7","Documentation, demonstration and slides may not match the final build","Process",3,4,"Open","Reduce","Team","Use the final accepted build as the single source for evidence","Screenshots or claims differ from the demonstrated build","Update documentation and slides from the accepted release","CWJ Sprint 4"),
            Risk("R8","Performance or reliability may be insufficient during demonstration","Technical",3,5,"Open","Reduce","Team","Test the demonstration environment and prepare a stable fallback build","Application freezes, slows or fails during rehearsal","Use the verified fallback build and local demonstration data","CWJ Sprint 4"),
            Risk("R9","Sprint 3 carryover may reduce capacity for Sprint 4 deliverables","Schedule",4,4,"Open","Reduce","Team","Confirm carryover, prioritise Must-Have work and assign owners","Unfinished Sprint 3 tasks enter the Sprint 4 plan","Defer nonessential refinement and protect testing/documentation","CWJ Sprint 4"),
        ]
        existing={r.risk_id for r in self.risks}
        for risk in suggestions:
            if risk.risk_id not in existing: self.risks.append(risk)
        self.save_data(silent=True); self.refresh_all()

    def import_database(self):
        path=filedialog.askopenfilename(title="Import CWJ JSON or SQLite database",filetypes=[("CWJ data","*.json *.sqlite *.sqlite3 *.db"),("All files","*.*")])
        if not path: return
        try:
            if path.lower().endswith(".json"): self.merge_payload(json.loads(Path(path).read_text(encoding="utf-8")))
            else: self.import_sqlite(path)
            self.save_data(silent=True); self.refresh_all(); messagebox.showinfo(APP_TITLE,"Data merged. Existing records were retained.")
        except Exception as exc: messagebox.showerror(APP_TITLE,f"Import failed:\n{exc}")
    def merge_payload(self,payload):
        for row in payload.get("stories",[]):
            try: story=Story(**row)
            except TypeError: continue
            key=story.source_id or story.title.casefold(); index=next((i for i,x in enumerate(self.stories) if (x.source_id or x.title.casefold())==key),None)
            if index is None: self.stories.append(story)
            else: self.stories[index]=story
        for row in payload.get("risks",[]):
            try: risk=Risk(**row)
            except TypeError: continue
            index=next((i for i,x in enumerate(self.risks) if x.risk_id==risk.risk_id),None)
            if index is None: self.risks.append(risk)
            else: self.risks[index]=risk
        if isinstance(payload.get("risk_snapshots"),list): self.risk_snapshots=payload["risk_snapshots"]
        if isinstance(payload.get("qa_tests"),list):
            self.qa_tests=[QATestCase(**row) for row in payload["qa_tests"] if isinstance(row,dict)]
        if isinstance(payload.get("kpis"),list): self.kpis=(payload["kpis"]+[self.blank_kpi() for _ in range(5)])[:5]
        if isinstance(payload.get("retrospective"),dict): self.retrospective.update(payload["retrospective"])
        settings=payload.get("settings",{}); self.current_sprint.set(settings.get("current_sprint",self.current_sprint.get())); self.sprint_goal.set(settings.get("sprint_goal",self.sprint_goal.get())); self.sprint_days.set(settings.get("sprint_days",self.sprint_days.get()))
        self.sync_kpi_widgets(); self.sync_retro_widgets()
    def import_sqlite(self,path):
        con=sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro",uri=True); con.row_factory=sqlite3.Row
        tables=[x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for table in tables:
            for row in con.execute(f'SELECT * FROM "{table}"'):
                data={k.lower():v for k,v in dict(row).items()}
                if any(k in data for k in ("title","story","summary","name")):
                    story=self.story_from_mapping(data,source=f"SQLite:{table}"); key=story.source_id or story.title.casefold()
                    if not any((x.source_id or x.title.casefold())==key for x in self.stories): self.stories.append(story)
                if "description" in data and ("likelihood" in data or "impact" in data):
                    risk=Risk(str(data.get("risk_id",data.get("id",f"R{len(self.risks)+1}"))),str(data["description"]),str(data.get("category","Project")),self.safe_int(data.get("likelihood",1),1),self.safe_int(data.get("impact",1),1),str(data.get("status","Open")),str(data.get("strategy","Reduce")),str(data.get("owner","")),str(data.get("response",data.get("mitigation",""))),str(data.get("trigger","")),str(data.get("contingency","")),str(data.get("sprint",self.current_sprint.get())))
                    if not any(x.risk_id==risk.risk_id for x in self.risks): self.risks.append(risk)
        con.close()
    def backup_data(self):
        folder=filedialog.askdirectory(title="Choose backup folder")
        if not folder: return
        self.capture_ui_state(); self.save_data(silent=True); destination=Path(folder)/f"CWJ_complete_backup_{datetime.now():%Y%m%d_%H%M%S}.json"; shutil.copy2(DATA_FILE,destination); messagebox.showinfo(APP_TITLE,f"Backup created:\n{destination}")
    def apply_sprint3_report(self):
        """Apply the confirmed Sprint 3 report without discarding other project data."""
        completed = {
            "cwj:CWJ-35": 3,
            "cwj:CWJ-60": 5,
            "cwj:CWJ-65": 1,
            "cwj:CWJ-66": 1,
            "cwj:CWJ-67": 1,
        }
        for story in self.stories:
            if story.sprint == "CWJ Sprint 3":
                if story.source_id in completed:
                    story.status = "Completed"
                    if story.completed_day <= 0:
                        story.completed_day = 15
                else:
                    story.status = "To Do"
                    story.completed_day = 0
        report_risks = {
            "R1": ("UI implementation may not match the agreed wireframe", "Requirements", 3, 3, "Open", "Reduce", "Aaron Davis"),
            "R2": ("Testing may be left too late, allowing defects to accumulate", "Quality", 4, 4, "Mitigated", "Accept", "Brendan Atherton"),
            "R3": ("GitHub, Jira, Confluence and local documentation may diverge", "Process", 3, 4, "Open", "Reduce", "Hannah Kingston"),
            "R4": ("Core features may remain unfinished at sprint end", "Schedule", 3, 5, "Open", "Reduce", "Brendan Atherton"),
        }
        for risk_id, values in report_risks.items():
            desc, category, likelihood, impact, status, strategy, owner = values
            risk = next((r for r in self.risks if r.risk_id == risk_id), None)
            if risk is None:
                risk = Risk(risk_id, desc, category, likelihood, impact, status, strategy, owner, sprint="CWJ Sprint 3")
                self.risks.append(risk)
            else:
                risk.description, risk.category, risk.likelihood, risk.impact = desc, category, likelihood, impact
                risk.status, risk.strategy, risk.owner, risk.sprint = status, strategy, owner, "CWJ Sprint 3"
        self.risk_snapshots = [x for x in self.risk_snapshots if not (x.get("sprint") == "CWJ Sprint 3" and x.get("source") == "Sprint 3 Report")]
        self.risk_snapshots.append({"time":"Sprint 3 report","sprint":"CWJ Sprint 3","exposure":52,"source":"Sprint 3 Report"})
        self.retrospective.update({
            "went_well": "Aaron and Brendan completed a short project discussion. UI Screens, Core features, Review risks, the Sprint 2 review and the Sprint 2 retrospective were recorded as completed, producing 11 completed story points.",
            "did_not_go_well": "Attendance and communication were limited. Hannah was unavailable because of work commitments, Harry was unable to attend, and personal family issues reduced Brendan's participation.",
            "start_doing": "Protect the final sprint by reviewing risks, carryover work and evidence needs early. Use short check-ins when full attendance is not possible.",
            "stop_doing": "Avoid further game programming unless later work makes it necessary. Do not add development scope that increases testing or completion risk.",
            "continue_doing": "Continue using the burn-up, burn-down and risk tools to make incomplete work and project exposure visible.",
            "blockers": "Limited communication, unavailable team members, work commitments and personal family issues affected Sprint 3 participation and progress.",
            "decisions": "No further game programming will occur unless it becomes necessary later. Risk 2 was treated as less significant for this project because the learning and development journey is more important than delivering a fully completed program.",
            "owners": "The team should confirm Sprint 4 owners for final documentation, testing, presentation, evidence and any carried-over Sprint 3 work.",
        })
        self.kpis = [
            {"name":"Sprint point completion rate","measure":"Completed points divided by planned points (%)","target":"80","actual":"39.3","action":"Review carryover and protect Sprint 4 Must-Have work"},
            {"name":"Sprint velocity","measure":"Completed story points in Sprint 3","target":"28","actual":"11","action":"Use actual capacity when planning Sprint 4"},
            {"name":"Carryover stories","measure":"Number of unfinished Sprint 3 stories","target":"0","actual":"6","action":"Prioritise or explicitly defer each carryover item"},
            {"name":"Active risk exposure","measure":"Sum of likelihood multiplied by impact for open Sprint 3 risks","target":"Reduce from baseline","actual":"52","action":"Review risk status and mitigation before Sprint 4 work"},
            {"name":"Completed stories","measure":"Number of Sprint 3 stories marked Completed","target":"11","actual":"5","action":"Keep partial work out of velocity and confirm acceptance criteria"},
        ]
        self.sync_kpi_widgets(); self.sync_retro_widgets()
        self.current_sprint.set("CWJ Sprint 4"); self.sprint_goal.set(28); self.sprint_days.set(15)
        self.save_data(silent=True); self.refresh_all()
        messagebox.showinfo(APP_TITLE, "Sprint 3 report applied. Sprint 3 actuals, KPIs, retrospective findings and risk results were saved. Sprint 4 is now selected.")

    def load_attached_results(self):
        bundled=Path(__file__).with_name("CWJ_backup_20261111_233702.json")
        if not bundled.exists(): messagebox.showerror(APP_TITLE,"The attached results JSON is not beside the Python program."); return
        self.merge_payload(json.loads(bundled.read_text(encoding="utf-8"))); self.current_sprint.set("CWJ Sprint 4"); self.sprint_goal.set(28); self.sprint_days.set(15); self.save_data(silent=True); self.refresh_all(); messagebox.showinfo(APP_TITLE,"Attached CWJ results loaded and Sprint 4 selected.")

    @staticmethod
    def blank_kpi(): return {"name":"","measure":"","target":"","actual":"","action":""}
    def sync_kpi_widgets(self):
        if hasattr(self,"kpi_vars"):
            for i,row in enumerate(self.kpis[:5]):
                for j,key in enumerate(("name","measure","target","actual","action")): self.kpi_vars[i][j].set(row.get(key,""))
    def sync_retro_widgets(self):
        if hasattr(self,"retro_widgets"):
            for key,widget in self.retro_widgets.items(): widget.delete("1.0","end"); widget.insert("1.0",self.retrospective.get(key,""))
    def capture_ui_state(self):
        if hasattr(self,"kpi_vars"):
            for i,variables in enumerate(self.kpi_vars): self.kpis[i]={"name":variables[0].get().strip(),"measure":variables[1].get().strip(),"target":variables[2].get().strip(),"actual":variables[3].get().strip(),"action":variables[4].get().strip()}
        if hasattr(self,"retro_widgets"):
            for key,widget in self.retro_widgets.items(): self.retrospective[key]=widget.get("1.0","end").strip()

    def _build_qa_tab(self):
        intro = ttk.Frame(self.qa_tab, style="Card.TFrame", padding=10)
        intro.pack(fill="x", padx=6, pady=(8, 4))
        ttk.Label(intro, text="Week 10 Quality Assurance - Software Testing", style="Card.TLabel", font=("Times New Roman", 16, "bold")).pack(anchor="w")
        ttk.Label(
            intro,
            text=("Testing evaluates and verifies that software does what it is intended to do. "
                  "It supports functional and non-functional requirements, defect detection, "
                  "performance, usability, security and confidence in the product."),
            style="Card.TLabel", wraplength=1120, justify="left"
        ).pack(anchor="w", pady=(4, 2))
        ttk.Label(
            intro,
            text=("Key principle: testing does not prove that defects are absent. It increases confidence "
                  "that the system works as intended under expected conditions."),
            style="Card.TLabel", foreground="#8b2d2d", wraplength=1120, justify="left"
        ).pack(anchor="w", pady=(2, 4))

        toolbar = ttk.Frame(self.qa_tab)
        toolbar.pack(fill="x", padx=6, pady=5)
        ttk.Button(toolbar, text="Load Week 10 CWJ Test Plan", command=self.load_week10_qa_plan).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Add Test Case", command=self.add_qa_test).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Edit Selected", command=self.edit_qa_test).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Mark Pass", command=lambda: self.set_qa_status("Pass")).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Mark Fail", command=lambda: self.set_qa_status("Fail")).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Mark Blocked", command=lambda: self.set_qa_status("Blocked")).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete Selected", command=self.delete_qa_test).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Export QA Report", command=self.export_qa_report).pack(side="right", padx=4)

        cols=("id","title","requirement","approach","method","status","owner")
        self.qa_tree=ttk.Treeview(self.qa_tab, columns=cols, show="headings", selectmode="extended", height=12)
        labels={"id":"Test ID","title":"Test case","requirement":"Requirement","approach":"Black/White box","method":"Manual/Automated","status":"Status","owner":"Owner"}
        widths={"id":75,"title":350,"requirement":110,"approach":120,"method":130,"status":95,"owner":130}
        for col in cols:
            self.qa_tree.heading(col,text=labels[col]); self.qa_tree.column(col,width=widths[col],anchor="w" if col in ("title","owner") else "center")
        self.qa_tree.pack(fill="both", expand=True, padx=8, pady=5)
        self.qa_tree.bind("<Double-1>", lambda _e: self.edit_qa_test())

        summary=ttk.Frame(self.qa_tab, style="Card.TFrame", padding=10)
        summary.pack(fill="x", padx=8, pady=(4,8))
        self.qa_summary=ttk.Label(summary, style="Card.TLabel", font=("Times New Roman", 13, "bold"))
        self.qa_summary.pack(anchor="w")
        ttk.Label(summary, text="Black-box tests evaluate behaviour without using internal code knowledge. White-box tests target internal paths or logic. Manual testing supports exploratory and UI/usability work; automated testing supports repeated validation and regression testing.", style="Card.TLabel", wraplength=1120, justify="left").pack(anchor="w", pady=(5,0))

    def load_week10_qa_plan(self):
        suggestions = [
            QATestCase("QA-01", "User can add a CWJ story with a valid Fibonacci point value", "Functional", "Black-box", "Manual", "CWJ program is open", "Open User Stories; choose Add Story; enter a title; choose a valid point value; save.", "The new story appears with the selected points and sprint.", owner="Team"),
            QATestCase("QA-02", "Only stories marked Completed contribute to velocity", "Functional", "Black-box", "Manual", "A sprint contains To Do and Completed stories", "Record the displayed velocity; change one selected story to Completed; enter a completion day; refresh.", "Velocity increases only by the completed story points; non-completed work contributes zero.", owner="Team"),
            QATestCase("QA-03", "Save and reload preserves Sprint 4 project information", "Functional", "Black-box", "Manual", "Stories, KPIs, retrospective, risks and QA cases exist", "Choose Save; close the program; reopen the same program.", "Saved project information reloads without losing existing CWJ records.", owner="Team"),
            QATestCase("QA-04", "Main tabs and QA controls remain readable at the supported minimum window size", "Non-functional", "Black-box", "Manual", "Program is running", "Resize the window to its minimum supported size; open each tab; inspect controls and scrolling.", "Important text, buttons, tables and scroll controls remain usable without overlapping or clipping.", owner="Team"),
            QATestCase("QA-05", "Typical local actions respond reliably without freezing the interface", "Non-functional", "Black-box", "Manual", "Program contains the CWJ project data", "Switch tabs; refresh charts; save data; generate the sprint report; repeat the sequence.", "The interface remains responsive and completes each local action consistently.", owner="Team"),
            QATestCase("QA-06", "Completed-status logic sets or clears completed_day correctly", "Functional", "White-box", "Automated", "Python unittest is available", "Test story status update logic with Completed and non-completed states.", "Completed work has a positive completed_day; other states use zero.", owner="Developer"),
            QATestCase("QA-07", "Risk exposure calculation returns likelihood multiplied by impact", "Functional", "White-box", "Automated", "Python unittest is available", "Create risks with known likelihood and impact values and evaluate exposure and active exposure.", "Exposure equals likelihood x impact; Closed or Resolved risks have zero active exposure.", owner="Developer"),
        ]
        existing={x.test_id for x in self.qa_tests}
        for item in suggestions:
            if item.test_id not in existing: self.qa_tests.append(item)
        self.save_data(silent=True); self.refresh_qa(); self.refresh_report()
        self.status_message.set("Week 10 quality assurance test plan loaded.")

    def add_qa_test(self): self.qa_test_dialog()
    def edit_qa_test(self):
        selected=self.qa_tree.selection()
        if selected: self.qa_test_dialog(int(selected[0]))
        else: messagebox.showinfo(APP_TITLE,"Select one QA test case to edit.")

    def qa_test_dialog(self,index=None):
        current=self.qa_tests[index] if index is not None else QATestCase(f"QA-{len(self.qa_tests)+1:02d}","")
        win=tk.Toplevel(self); win.title("Quality Assurance Test Case"); win.transient(self); win.grab_set(); win.configure(bg="#dcefff")
        outer=ttk.Frame(win,style="Card.TFrame",padding=14); outer.pack(fill="both",expand=True,padx=12,pady=12)
        specs=[("Test ID",current.test_id,None),("Title",current.title,None),("Requirement type",current.requirement_type,["Functional","Non-functional"]),("Test approach",current.test_approach,["Black-box","White-box"]),("Execution method",current.execution_method,["Manual","Automated"]),("Status",current.status,["Not Run","Pass","Fail","Blocked"]),("Owner",current.owner,None),("Preconditions",current.preconditions,None),("Test steps",current.steps,None),("Expected result",current.expected_result,None),("Actual result",current.actual_result,None),("Evidence / reference",current.evidence,None)]
        variables=[]
        for row,(label,value,choices) in enumerate(specs):
            ttk.Label(outer,text=label,style="Card.TLabel").grid(row=row,column=0,sticky="nw",padx=4,pady=4)
            var=tk.StringVar(value=value); variables.append(var)
            widget=ttk.Combobox(outer,textvariable=var,values=choices,state="readonly",width=70) if choices else ttk.Entry(outer,textvariable=var,width=73)
            widget.grid(row=row,column=1,sticky="ew",padx=4,pady=4)
        def save_case():
            vals=[v.get().strip() for v in variables]
            if not vals[1]: messagebox.showerror(APP_TITLE,"Enter a test-case title.",parent=win); return
            item=QATestCase(vals[0] or f"QA-{len(self.qa_tests)+1:02d}",vals[1],vals[2],vals[3],vals[4],vals[7],vals[8],vals[9],vals[10],vals[5],vals[11],vals[6])
            if index is None: self.qa_tests.append(item)
            else: self.qa_tests[index]=item
            self.save_data(silent=True); self.refresh_qa(); self.refresh_report(); win.destroy()
        ttk.Button(outer,text="Save Test Case",command=save_case).grid(row=len(specs),column=0,columnspan=2,pady=10)

    def set_qa_status(self,status):
        selected=self.qa_tree.selection()
        if not selected: messagebox.showinfo(APP_TITLE,"Select at least one QA test case."); return
        for item in selected: self.qa_tests[int(item)].status=status
        self.save_data(silent=True); self.refresh_qa(); self.refresh_report()

    def delete_qa_test(self):
        selected=self.qa_tree.selection()
        if not selected or not messagebox.askyesno(APP_TITLE,"Delete the selected QA test cases?"): return
        for index in sorted((int(x) for x in selected),reverse=True): del self.qa_tests[index]
        self.save_data(silent=True); self.refresh_qa(); self.refresh_report()

    def refresh_qa(self):
        if not hasattr(self,"qa_tree"): return
        for item in self.qa_tree.get_children(): self.qa_tree.delete(item)
        for index,test in enumerate(self.qa_tests):
            self.qa_tree.insert("","end",iid=str(index),values=(test.test_id,test.title,test.requirement_type,test.test_approach,test.execution_method,test.status,test.owner))
        total=len(self.qa_tests); passed=sum(x.status=="Pass" for x in self.qa_tests); failed=sum(x.status=="Fail" for x in self.qa_tests); blocked=sum(x.status=="Blocked" for x in self.qa_tests); pending=sum(x.status=="Not Run" for x in self.qa_tests)
        self.qa_summary.config(text=f"QA cases: {total} | Pass: {passed} | Fail: {failed} | Blocked: {blocked} | Not Run: {pending}")

    def qa_report_lines(self):
        if not self.qa_tests: return ["- No QA test cases recorded"]
        lines=[]
        for test in self.qa_tests:
            lines.append(f"- {test.test_id}: {test.title} | {test.requirement_type} | {test.test_approach} | {test.execution_method} | {test.status}")
        return lines

    def build_qa_report_text(self):
        headings=["QUALITY ASSURANCE TEST REPORT","="*70,"Week 10 focus: software testing, functional/non-functional testing, black-box/white-box testing, and manual/automated testing.",""]
        for test in self.qa_tests:
            headings.extend([f"{test.test_id} - {test.title}",f"Requirement: {test.requirement_type}",f"Approach: {test.test_approach}",f"Execution: {test.execution_method}",f"Status: {test.status}",f"Owner: {test.owner or 'Not assigned'}",f"Preconditions: {test.preconditions or 'Not entered'}",f"Steps: {test.steps or 'Not entered'}",f"Expected: {test.expected_result or 'Not entered'}",f"Actual: {test.actual_result or 'Not entered'}",f"Evidence: {test.evidence or 'Not entered'}",""])
        return "\n".join(headings)

    def export_qa_report(self):
        path=filedialog.asksaveasfilename(defaultextension=".txt",filetypes=[("Text report","*.txt")],initialfile="CWJ_Sprint_4_QA_Report.txt")
        if path:
            Path(path).write_text(self.build_qa_report_text(),encoding="utf-8")
            self.status_message.set(f"QA report exported to {Path(path).name}.")

    def _build_help_tab(self):
        help_text = """HOW TO USE THE PROGRAM

A. Add stories
1. Choose Add Story.
2. Enter the story or task name.
3. Choose a Fibonacci story-point value: 1, 2, 3, 5, 8, 13 or 21.
4. Choose the sprint and current status.

B. Completed work rule
Only a story with the exact status Completed contributes to:
• achieved points
• sprint velocity
• burn-up progress
• burn-down reduction

A story that is Backlog, To Do, In Progress or Blocked contributes zero completed points.
Partially completed stories also contribute zero until the entire story meets its acceptance criteria.

C. Completed day
For a completed story, enter the sprint day on which it was accepted as complete.
Example: if a 5-point story was completed on Day 3, the burn-up chart increases by 5 on Day 3 and the burn-down chart decreases by 5.

D. Burn-down chart
• Starts at the sprint goal.
• Moves downward as completed points are recorded.
• The ideal line moves evenly from the goal to zero.
• Actual above ideal usually means less work has been completed than planned.

E. Burn-up chart
• Starts at zero.
• Moves upward as completed points are recorded.
• The goal line represents the planned sprint scope.

F. GitHub import
The importer reads repository issues. Closed issues become Completed and open issues become To Do.
Pull requests are ignored. Story points can be read from labels such as points:5, story-points:5, sp:5, or a body line such as Story Points: 5.
Check the imported data because GitHub's closed state does not automatically prove that your team's acceptance criteria were met.

G. ZIP import and export
Import ZIP scans a Sprint ZIP for supported CSV, JSON, TXT, Markdown and Word-compatible DOC files.
It imports structured story records from CSV/JSON and can detect user-story sentences in documentation.
Detected documentation stories receive 0 points so the team must agree on an estimate before points are counted.
The importer also looks for completion wording, but every imported result should be reviewed by the team.
Export ZIP creates a portable package containing your stories as JSON and CSV plus a text sprint summary.

H. Jira import
Import Jira asks for the Jira Cloud site, Atlassian account email, API token and Sprint ID.
It imports the sprint name, sprint goal, dates, issues, assignees, statuses and available story points.
Only Jira issues whose status category is Done are imported as Completed.
The email and API token are used for the current request only and are not saved.

I. KPIs, retrospective and sprint report
The KPI page provides five editable placeholders. A KPI is marked useful when it has a name, measure, target and action.
The retrospective page links discussion to completed stories, unfinished work, blockers and KPI results.
The sprint report combines story totals, velocity, completion rate, KPI entries, carryover and agreed actions.

J. CWJ preloaded catalog
Use Load CWJ 67-Task Catalog to populate all four Conquest World sprints. The Project Velocity tab shows cross-sprint burn-up, burn-down, completed scope, remaining scope and historical average velocity.

K. Integrated risk management
The Risk Management tab records likelihood, impact, exposure, owner, response, trigger and contingency. Risk exposure is likelihood multiplied by impact. Closed and resolved risks count as zero active exposure.
L. Complete data continuity
The application preserves stories, KPIs, retrospective entries, risks and exposure snapshots in one JSON file. Import JSON/SQLite merges data. Backup All Data creates a timestamped complete copy.
M. Sprint 3 report
Apply Sprint 3 Report records 11 completed points, 17 remaining points, the five completed tasks, the 52 risk exposure result, the retrospective discussion, attendance constraints and the decision not to add further game programming unless necessary.
N. Sprint 4
Load Attached Results imports the supplied backup, retains updated Sprint 3 results, selects Sprint 4 and preserves the 28-point Sprint 4 plan.
O. Week 10 Quality Assurance
The Quality Assurance tab records functional and non-functional tests, black-box and white-box approaches, manual and automated execution, expected and actual results, evidence, ownership and Pass/Fail/Blocked/Not Run status.
Use Load Week 10 CWJ Test Plan to add a starting test plan without removing existing CWJ stories, KPIs, retrospective entries or risks.
P. Saving
The program saves its local data in your user folder as agile_story_points_data.json.
GitHub and Jira credentials are never stored in that file.
"""
        text = tk.Text(self.help_tab, wrap="word", font=("Times New Roman", 14), bg="white", padx=18, pady=15)
        text.pack(fill="both", expand=True, padx=5, pady=5)
        text.insert("1.0", help_text)
        text.configure(state="disabled")

    def filtered_stories(self):
        sprint = self.current_sprint.get().strip()
        return [story for story in self.stories if story.sprint == sprint]

    def refresh_all(self):
        self.refresh_tree()
        self.refresh_metrics()
        self.refresh_risks()
        self.refresh_qa()
        self.refresh_report()
        self.after(50, self.draw_charts)
        self.after(70, self.draw_project_charts)

    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, story in enumerate(self.stories):
            self.tree.insert("", "end", iid=str(index), values=(
                story.title, story.points, story.status, story.sprint,
                story.completed_day or "", story.assignee, story.source
            ))

    def refresh_metrics(self):
        stories = self.filtered_stories()
        planned = sum(s.points for s in stories)
        completed = sum(s.points for s in stories if s.is_completed)
        goal = max(1, self.safe_int(self.sprint_goal.get(), 1))
        percent = min(100.0, completed / goal * 100)
        completed_count = sum(1 for s in stories if s.is_completed)
        self.metric_total.config(text=f"Planned: {planned} pts")
        self.metric_completed.config(text=f"Completed: {completed_count} stories / {completed} pts")
        self.metric_velocity.config(text=f"Velocity: {completed} pts")
        self.metric_progress.config(text=f"Goal progress: {percent:.1f}%")

    @staticmethod
    def safe_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def add_story(self):
        self.story_dialog()

    def edit_story(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo(APP_TITLE, "Select one story to edit.")
            return
        self.story_dialog(int(selected[0]))

    def story_dialog(self, index=None):
        existing = self.stories[index] if index is not None else Story("", 3, sprint=self.current_sprint.get())
        window = tk.Toplevel(self)
        window.title("Edit Story" if index is not None else "Add Story")
        window.transient(self)
        window.grab_set()
        window.configure(bg="#dcefff")

        fields = ttk.Frame(window, style="Card.TFrame", padding=16)
        fields.pack(fill="both", expand=True, padx=12, pady=12)

        title_var = tk.StringVar(value=existing.title)
        points_var = tk.IntVar(value=existing.points)
        status_var = tk.StringVar(value=existing.status)
        sprint_var = tk.StringVar(value=existing.sprint)
        day_var = tk.StringVar(value=str(existing.completed_day or ""))
        assignee_var = tk.StringVar(value=existing.assignee)

        labels = ["Story / task:", "Story points:", "Status:", "Sprint:", "Completed day:", "Assignee:"]
        for row, label in enumerate(labels):
            ttk.Label(fields, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", padx=5, pady=7)

        ttk.Entry(fields, textvariable=title_var, width=52).grid(row=0, column=1, padx=5, pady=7)
        ttk.Combobox(fields, textvariable=points_var, values=FIBONACCI_POINTS, state="readonly", width=12).grid(row=1, column=1, sticky="w", padx=5, pady=7)
        ttk.Combobox(fields, textvariable=status_var, values=STATUSES, state="readonly", width=18).grid(row=2, column=1, sticky="w", padx=5, pady=7)
        ttk.Combobox(fields, textvariable=sprint_var, values=[f"Sprint {i}" for i in range(1, 13)] + [f"CWJ Sprint {i}" for i in range(1,5)], width=18).grid(row=3, column=1, sticky="w", padx=5, pady=7)
        ttk.Entry(fields, textvariable=day_var, width=14).grid(row=4, column=1, sticky="w", padx=5, pady=7)
        ttk.Entry(fields, textvariable=assignee_var, width=30).grid(row=5, column=1, sticky="w", padx=5, pady=7)

        def save_story():
            title = title_var.get().strip()
            if not title:
                messagebox.showerror(APP_TITLE, "Enter a story or task name.", parent=window)
                return
            status = status_var.get()
            day = self.safe_int(day_var.get(), 0)
            if status == "Completed" and day <= 0:
                day = 1
            if status != "Completed":
                day = 0
            story = Story(
                title=title,
                points=int(points_var.get()),
                status=status,
                sprint=sprint_var.get().strip() or "Sprint 1",
                completed_day=day,
                assignee=assignee_var.get().strip(),
                source=existing.source,
                source_id=existing.source_id,
            )
            if index is None:
                self.stories.append(story)
            else:
                self.stories[index] = story
            self.save_data(silent=True)
            self.refresh_all()
            window.destroy()

        ttk.Button(fields, text="Save Story", command=save_story).grid(row=6, column=0, columnspan=2, pady=14)

    def set_selected_status(self, status):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo(APP_TITLE, "Select at least one story.")
            return
        day = 0
        if status == "Completed":
            day = simpledialog.askinteger("Completed day", "On which sprint day was this work accepted as complete?", minvalue=1, maxvalue=999, parent=self)
            if day is None:
                return
        for item in selected:
            story = self.stories[int(item)]
            story.status = status
            story.completed_day = day if status == "Completed" else 0
        self.save_data(silent=True)
        self.refresh_all()

    def delete_story(self):
        selected = self.tree.selection()
        if not selected:
            return
        if not messagebox.askyesno(APP_TITLE, "Delete the selected stories?"):
            return
        for index in sorted((int(item) for item in selected), reverse=True):
            del self.stories[index]
        self.save_data(silent=True)
        self.refresh_all()

    def save_data(self, silent=False):
        self.capture_ui_state()
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "settings": {
                "sprint_days": self.safe_int(self.sprint_days.get(), 10),
                "sprint_goal": self.safe_int(self.sprint_goal.get(), 30),
                "current_sprint": self.current_sprint.get(),
            },
            "stories": [asdict(story) for story in self.stories],
            "kpis": self.kpis,
            "retrospective": self.retrospective,
            "risks": [asdict(risk) for risk in self.risks],
            "risk_snapshots": self.risk_snapshots,
            "qa_tests": [asdict(test) for test in self.qa_tests],
        }
        try:
            DATA_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            if not silent:
                self.status_message.set(f"Saved locally to {DATA_FILE}")
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Could not save data:\n{exc}")

    def load_data(self, silent=False):
        if not DATA_FILE.exists():
            return
        try:
            payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            self.stories = [Story(**row) for row in payload.get("stories", [])]
            loaded_kpis = payload.get("kpis")
            if isinstance(loaded_kpis, list):
                self.kpis = (loaded_kpis + [{"name":"", "measure":"", "target":"", "actual":"", "action":""}] * 5)[:5]
            loaded_retro = payload.get("retrospective")
            if isinstance(loaded_retro, dict):
                self.retrospective.update(loaded_retro)
            loaded_risks = payload.get("risks", [])
            if isinstance(loaded_risks, list): self.risks = [Risk(**row) for row in loaded_risks if isinstance(row, dict)]
            self.risk_snapshots = payload.get("risk_snapshots", []) if isinstance(payload.get("risk_snapshots", []), list) else []
            loaded_qa = payload.get("qa_tests", [])
            if isinstance(loaded_qa, list): self.qa_tests = [QATestCase(**row) for row in loaded_qa if isinstance(row, dict)]
            settings = payload.get("settings", {})
            self.sprint_days.set(settings.get("sprint_days", 10))
            self.sprint_goal.set(settings.get("sprint_goal", 30))
            self.current_sprint.set(settings.get("current_sprint", "Sprint 1"))
            if not silent:
                self.status_message.set(f"Loaded {len(self.stories)} stories.")
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror(APP_TITLE, f"Could not load saved data:\n{exc}")

    def import_file(self):
        path = filedialog.askopenfilename(filetypes=[("CSV or JSON", "*.csv *.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            imported = []
            if path.lower().endswith(".json"):
                raw = json.loads(Path(path).read_text(encoding="utf-8"))
                rows = raw.get("stories", raw) if isinstance(raw, dict) else raw
                for row in rows:
                    imported.append(self.story_from_mapping(row, source="JSON"))
            else:
                with open(path, newline="", encoding="utf-8-sig") as file:
                    for row in csv.DictReader(file):
                        imported.append(self.story_from_mapping(row, source="CSV"))
            self.stories.extend(imported)
            self.save_data(silent=True)
            self.refresh_all()
            self.status_message.set(f"Imported {len(imported)} stories from {Path(path).name}.")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Import failed:\n{exc}")

    def story_from_mapping(self, row, source="Import"):
        status = str(row.get("status", row.get("state", "Backlog"))).strip().lower()
        if status in ("done", "complete", "completed", "closed"):
            status = "Completed"
        elif status in ("in progress", "in_progress", "doing"):
            status = "In Progress"
        elif status == "blocked":
            status = "Blocked"
        elif status in ("to do", "todo", "open"):
            status = "To Do"
        else:
            status = "Backlog"
        return Story(
            title=str(row.get("title", row.get("story", row.get("name", "Imported story")))).strip(),
            points=max(0, self.safe_int(row.get("points", row.get("story_points", 0)), 0)),
            status=status,
            sprint=str(row.get("sprint", self.current_sprint.get())).strip() or self.current_sprint.get(),
            completed_day=max(0, self.safe_int(row.get("completed_day", row.get("day", 0)), 0)),
            assignee=str(row.get("assignee", "")).strip(),
            source=source,
            source_id=str(row.get("source_id", "")),
        )

    def import_zip(self):
        path = filedialog.askopenfilename(
            title="Choose a Sprint ZIP folder",
            filetypes=[("ZIP folders", "*.zip"), ("All files", "*.*")],
        )
        if not path:
            return
        imported = []
        notes = []
        try:
            with zipfile.ZipFile(path, "r") as archive:
                names = archive.namelist()
                for name in names:
                    if name.endswith("/"):
                        continue
                    lower = name.lower()
                    raw = archive.read(name)
                    if lower.endswith(".json"):
                        try:
                            obj = json.loads(raw.decode("utf-8-sig"))
                            rows = obj.get("stories", obj) if isinstance(obj, dict) else obj
                            if isinstance(rows, list):
                                for row in rows:
                                    if isinstance(row, dict):
                                        imported.append(self.story_from_mapping(row, source=f"ZIP:{Path(name).name}"))
                        except Exception as exc:
                            notes.append(f"Could not read JSON {name}: {exc}")
                    elif lower.endswith(".csv"):
                        try:
                            text = raw.decode("utf-8-sig", errors="replace")
                            for row in csv.DictReader(text.splitlines()):
                                imported.append(self.story_from_mapping(row, source=f"ZIP:{Path(name).name}"))
                        except Exception as exc:
                            notes.append(f"Could not read CSV {name}: {exc}")
                    elif lower.endswith((".txt", ".md", ".doc")):
                        text = raw.decode("utf-8", errors="ignore")
                        imported.extend(self.extract_stories_from_document(text, Path(name).name))

            # Deduplicate by title, sprint and source ID.
            existing_keys = {(x.title.casefold(), x.sprint.casefold(), x.source_id) for x in self.stories}
            unique = []
            for story in imported:
                key = (story.title.casefold(), story.sprint.casefold(), story.source_id)
                if key not in existing_keys:
                    existing_keys.add(key)
                    unique.append(story)
            self.stories.extend(unique)
            self.save_data(silent=True)
            self.refresh_all()
            summary = f"Imported {len(unique)} story records from {Path(path).name}."
            if notes:
                summary += f"\n\n{len(notes)} file notes were recorded."
            summary += "\n\nReview statuses and assign Fibonacci points before using the charts."
            messagebox.showinfo(APP_TITLE, summary)
            self.status_message.set(summary.split("\n")[0])
        except zipfile.BadZipFile:
            messagebox.showerror(APP_TITLE, "The selected file is not a readable ZIP folder.")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"ZIP import failed:\n{exc}")

    def extract_stories_from_document(self, text, filename):
        """Detect user-story sentences and selected development tasks in plain document text."""
        found = []
        clean = text.replace("\r", "\n")
        # User stories may be bullets or paragraphs beginning with 'As a/an'.
        pattern = re.compile(
            r"(?:^|\n)\s*[-*•]?\s*(As an?\s+.+?\bso (?:that )?.+?)(?=\n\s*[-*•]?\s*As an?\s+|\n\s*[A-Z][^\n]{0,60}:?\s*$|\Z)",
            re.IGNORECASE | re.DOTALL | re.MULTILINE,
        )
        for match in pattern.finditer(clean):
            title = " ".join(match.group(1).split())
            title = title[:500]
            found.append(Story(
                title=title,
                points=0,
                status="Backlog",
                sprint=self.current_sprint.get() or "Sprint 2",
                source=f"ZIP document:{filename}",
            ))

        # Recognise explicit completion statements in team documentation.
        completion_match = re.search(
            r"Code key features[,\s]+(.+?)[;.]?\s*were done",
            clean,
            re.IGNORECASE | re.DOTALL,
        )
        if completion_match:
            chunk = " ".join(completion_match.group(1).split())
            for item in re.split(r",|;|\band\b", chunk):
                item = item.strip(" .")
                if item:
                    found.append(Story(
                        title=item,
                        points=0,
                        status="Completed",
                        sprint=self.current_sprint.get() or "Sprint 2",
                        completed_day=1,
                        source=f"ZIP completion note:{filename}",
                    ))
        return found

    def export_zip(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP folders", "*.zip")],
            initialfile=f"{self.current_sprint.get().replace(' ', '_')}_Agile_Package.zip",
        )
        if not path:
            return
        stories = self.stories
        selected = self.filtered_stories()
        completed_points = sum(x.points for x in selected if x.is_completed)
        planned_points = sum(x.points for x in selected)
        goal = self.safe_int(self.sprint_goal.get(), 0)
        summary = (
            f"Agile Story Points Studio Export\n"
            f"Sprint: {self.current_sprint.get()}\n"
            f"Sprint goal: {goal} points\n"
            f"Planned story points: {planned_points}\n"
            f"Completed story points / velocity: {completed_points}\n"
            f"Rule: Only Completed stories count toward achieved points.\n"
        )
        payload = {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "settings": {
                "sprint_days": self.safe_int(self.sprint_days.get(), 10),
                "sprint_goal": goal,
                "current_sprint": self.current_sprint.get(),
            },
            "stories": [asdict(x) for x in stories],
            "kpis": self.kpis, "retrospective": self.retrospective,
            "risks": [asdict(x) for x in self.risks], "risk_snapshots": self.risk_snapshots,
            "qa_tests": [asdict(test) for test in self.qa_tests],
        }
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            json_path = folder / "stories.json"
            csv_path = folder / "stories.csv"
            txt_path = folder / "sprint_summary.txt"
            json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            txt_path.write_text(summary, encoding="utf-8")
            fields = ["title", "points", "status", "sprint", "completed_day", "assignee", "source", "source_id"]
            with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                for story in stories:
                    writer.writerow(asdict(story))
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(json_path, json_path.name)
                archive.write(csv_path, csv_path.name)
                archive.write(txt_path, txt_path.name)
        self.status_message.set(f"Exported portable Sprint ZIP: {Path(path).name}")
        messagebox.showinfo(APP_TITLE, "Sprint ZIP exported with JSON, CSV and a text summary.")

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="agile_story_points.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            fields = ["title", "points", "status", "sprint", "completed_day", "assignee", "source", "source_id"]
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for story in self.stories:
                writer.writerow(asdict(story))
        self.status_message.set(f"Exported stories to {Path(path).name}.")

    def import_jira_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Import Jira Sprint")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg="#dcefff")
        frame = ttk.Frame(dialog, style="Card.TFrame", padding=16)
        frame.pack(padx=12, pady=12)

        site_var = tk.StringVar(value="https://student-team-ecvn69ll.atlassian.net")
        email_var = tk.StringVar()
        token_var = tk.StringVar()
        sprint_id_var = tk.StringVar()
        points_field_var = tk.StringVar()

        rows = [
            ("Jira Cloud site:", ttk.Entry(frame, textvariable=site_var, width=48)),
            ("Atlassian account email:", ttk.Entry(frame, textvariable=email_var, width=38)),
            ("Jira API token:", ttk.Entry(frame, textvariable=token_var, width=38, show="*")),
            ("Sprint ID:", ttk.Entry(frame, textvariable=sprint_id_var, width=16)),
            ("Story-points field ID (optional):", ttk.Entry(frame, textvariable=points_field_var, width=20)),
        ]
        for row, (label, widget) in enumerate(rows):
            ttk.Label(frame, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", padx=5, pady=7)
            widget.grid(row=row, column=1, sticky="w", padx=5, pady=7)

        explanation = (
            "The importer reads sprint metadata and issues. It attempts to find the Story Points field automatically.\n"
            "Only issues in Jira's Done status category count as Completed. Credentials are not saved."
        )
        ttk.Label(frame, text=explanation, style="Card.TLabel", foreground="#8b2d2d").grid(
            row=5, column=0, columnspan=2, sticky="w", padx=5, pady=9
        )

        def run_import():
            site = site_var.get().strip().rstrip("/")
            email = email_var.get().strip()
            token = token_var.get().strip()
            sprint_id = self.safe_int(sprint_id_var.get(), 0)
            if not site.startswith("https://") or not email or not token or sprint_id <= 0:
                messagebox.showerror(APP_TITLE, "Enter an HTTPS Jira site, email, API token and numeric Sprint ID.", parent=dialog)
                return
            try:
                result = self.import_jira_sprint(site, email, token, sprint_id, points_field_var.get().strip())
                token_var.set("")
                dialog.destroy()
                messagebox.showinfo(
                    APP_TITLE,
                    f"Imported or updated {result['issues']} Jira issues from {result['sprint']}.\n"
                    f"Sprint goal: {result['goal'] or 'No goal supplied'}\n\n"
                    "Review imported statuses, points and completion days before relying on the charts.",
                )
            except Exception as exc:
                token_var.set("")
                messagebox.showerror(APP_TITLE, f"Jira import failed:\n{exc}", parent=dialog)

        ttk.Button(frame, text="Import Jira Sprint", command=run_import).grid(row=6, column=0, columnspan=2, pady=12)

    @staticmethod
    def jira_request(site, email, token, endpoint):
        credential = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
        request = urllib.request.Request(
            f"{site}{endpoint}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Basic {credential}",
                "User-Agent": "Agile-Story-Points-Studio",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Jira returned HTTP {exc.code}: {detail[:400]}") from exc

    @staticmethod
    def jira_text(value):
        """Convert plain Jira text or Atlassian Document Format into readable text."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return " ".join(AgileStudio.jira_text(item) for item in value).strip()
        if isinstance(value, dict):
            if value.get("type") == "text":
                return str(value.get("text", ""))
            return " ".join(AgileStudio.jira_text(item) for item in value.get("content", [])).strip()
        return str(value)

    def import_jira_sprint(self, site, email, token, sprint_id, supplied_points_field=""):
        sprint = self.jira_request(site, email, token, f"/rest/agile/1.0/sprint/{sprint_id}")
        fields = self.jira_request(site, email, token, "/rest/api/3/field")

        points_field = supplied_points_field
        if not points_field:
            preferred = ("story points", "story point estimate")
            for field in fields:
                if str(field.get("name", "")).strip().casefold() in preferred:
                    points_field = field.get("id", "")
                    break

        issue_fields = ["summary", "description", "status", "assignee", "resolutiondate", "created", "updated"]
        if points_field:
            issue_fields.append(points_field)
        encoded_fields = urllib.parse.quote(",".join(issue_fields), safe=",")

        all_issues = []
        start_at = 0
        while True:
            endpoint = (
                f"/rest/agile/1.0/sprint/{sprint_id}/issue"
                f"?startAt={start_at}&maxResults=100&fields={encoded_fields}"
            )
            page = self.jira_request(site, email, token, endpoint)
            issues = page.get("issues", [])
            all_issues.extend(issues)
            start_at += len(issues)
            if not issues or start_at >= int(page.get("total", start_at)):
                break

        sprint_name = sprint.get("name") or f"Jira Sprint {sprint_id}"
        sprint_goal_text = sprint.get("goal") or ""
        self.current_sprint.set(sprint_name)

        start_date = None
        end_date = None
        try:
            if sprint.get("startDate"):
                start_date = datetime.fromisoformat(sprint["startDate"].replace("Z", "+00:00"))
            if sprint.get("endDate"):
                end_date = datetime.fromisoformat(sprint["endDate"].replace("Z", "+00:00"))
            if start_date and end_date:
                self.sprint_days.set(max(1, (end_date.date() - start_date.date()).days + 1))
        except ValueError:
            start_date = end_date = None

        imported = 0
        imported_points_total = 0
        for issue in all_issues:
            item_fields = issue.get("fields", {})
            status_obj = item_fields.get("status") or {}
            status_category = status_obj.get("statusCategory") or {}
            is_done = str(status_category.get("key", "")).casefold() == "done"
            points_value = item_fields.get(points_field) if points_field else 0
            try:
                points = int(float(points_value)) if points_value is not None else 0
            except (TypeError, ValueError):
                points = 0
            imported_points_total += points

            completed_day = 0
            if is_done:
                completed_day = 1
                try:
                    resolution = item_fields.get("resolutiondate")
                    if start_date and resolution:
                        resolved_dt = datetime.fromisoformat(resolution.replace("Z", "+00:00"))
                        completed_day = max(1, (resolved_dt.date() - start_date.date()).days + 1)
                        completed_day = min(self.safe_int(self.sprint_days.get(), 10), completed_day)
                except ValueError:
                    completed_day = 1

            assignee = item_fields.get("assignee") or {}
            source_id = f"jira:{site}:{issue.get('key')}"
            story = Story(
                title=f"{issue.get('key', '')} - {item_fields.get('summary', 'Untitled issue')}".strip(" -"),
                points=points,
                status="Completed" if is_done else self.map_jira_status(status_obj),
                sprint=sprint_name,
                completed_day=completed_day,
                assignee=assignee.get("displayName", "") if isinstance(assignee, dict) else "",
                source="Jira",
                source_id=source_id,
            )
            existing_index = next((i for i, old in enumerate(self.stories) if old.source_id == source_id), None)
            if existing_index is None:
                self.stories.append(story)
            else:
                old = self.stories[existing_index]
                if is_done and old.completed_day > 0:
                    story.completed_day = old.completed_day
                self.stories[existing_index] = story
            imported += 1

        if imported_points_total > 0:
            self.sprint_goal.set(imported_points_total)
        self.save_data(silent=True)
        self.refresh_all()
        self.status_message.set(f"Imported {imported} Jira issues from {sprint_name}.")
        return {"issues": imported, "sprint": sprint_name, "goal": sprint_goal_text, "points_field": points_field}

    @staticmethod
    def map_jira_status(status_obj):
        category = (status_obj.get("statusCategory") or {}).get("key", "")
        name = str(status_obj.get("name", "")).casefold()
        if category == "done":
            return "Completed"
        if "block" in name:
            return "Blocked"
        if category == "indeterminate":
            return "In Progress"
        if category == "new":
            return "To Do"
        return "Backlog"

    def import_github_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Import GitHub Issues")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg="#dcefff")
        frame = ttk.Frame(dialog, style="Card.TFrame", padding=16)
        frame.pack(padx=12, pady=12)

        repo_var = tk.StringVar()
        token_var = tk.StringVar()
        sprint_var = tk.StringVar(value=self.current_sprint.get())
        default_points_var = tk.IntVar(value=3)

        fields = [
            ("Repository (owner/name):", ttk.Entry(frame, textvariable=repo_var, width=42)),
            ("Fine-grained token (optional for public repo):", ttk.Entry(frame, textvariable=token_var, width=42, show="*")),
            ("Import into sprint:", ttk.Entry(frame, textvariable=sprint_var, width=20)),
            ("Default points when none found:", ttk.Combobox(frame, textvariable=default_points_var, values=FIBONACCI_POINTS, state="readonly", width=10)),
        ]
        for row, (label, widget) in enumerate(fields):
            ttk.Label(frame, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", padx=5, pady=7)
            widget.grid(row=row, column=1, sticky="w", padx=5, pady=7)

        ttk.Label(frame, text="Closed issues import as Completed; open issues import as To Do.\nPull requests are ignored. Verify acceptance criteria after import.", style="Card.TLabel", foreground="#8b2d2d").grid(row=4, column=0, columnspan=2, sticky="w", padx=5, pady=8)

        def run_import():
            repo = repo_var.get().strip().strip("/")
            if repo.count("/") != 1:
                messagebox.showerror(APP_TITLE, "Enter the repository as owner/name.", parent=dialog)
                return
            try:
                count = self.import_github_issues(repo, token_var.get().strip(), sprint_var.get().strip(), int(default_points_var.get()))
                dialog.destroy()
                messagebox.showinfo(APP_TITLE, f"Imported or updated {count} GitHub issues.\nPlease verify that closed issues meet your team's definition of completed.")
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"GitHub import failed:\n{exc}", parent=dialog)

        ttk.Button(frame, text="Import Issues", command=run_import).grid(row=5, column=0, columnspan=2, pady=12)

    def import_github_issues(self, repo, token, sprint, default_points):
        page = 1
        imported_count = 0
        while True:
            query = urllib.parse.urlencode({"state": "all", "per_page": 100, "page": page})
            url = f"https://api.github.com/repos/{repo}/issues?{query}"
            headers = {
                "Accept": "application/vnd.github+json",
                "User-Agent": "Agile-Story-Points-Studio",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=25) as response:
                    issues = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"GitHub returned HTTP {exc.code}: {detail[:300]}") from exc

            if not issues:
                break
            for issue in issues:
                if "pull_request" in issue:
                    continue
                issue_id = f"github:{repo}#{issue.get('number')}"
                points = self.extract_story_points(issue, default_points)
                state = issue.get("state", "open")
                completed = state == "closed"
                completed_day = 1 if completed else 0
                assignees = ", ".join(a.get("login", "") for a in issue.get("assignees", []))
                story = Story(
                    title=issue.get("title", f"Issue #{issue.get('number')}"),
                    points=points,
                    status="Completed" if completed else "To Do",
                    sprint=sprint or self.current_sprint.get(),
                    completed_day=completed_day,
                    assignee=assignees,
                    source="GitHub",
                    source_id=issue_id,
                )
                existing_index = next((i for i, s in enumerate(self.stories) if s.source_id == issue_id), None)
                if existing_index is None:
                    self.stories.append(story)
                else:
                    old = self.stories[existing_index]
                    if old.completed_day > 0 and completed:
                        story.completed_day = old.completed_day
                    self.stories[existing_index] = story
                imported_count += 1
            if len(issues) < 100:
                break
            page += 1
        self.save_data(silent=True)
        self.refresh_all()
        return imported_count

    @staticmethod
    def extract_story_points(issue, default_points):
        labels = [label.get("name", "") for label in issue.get("labels", [])]
        patterns = [r"(?:story[-_ ]?points?|points?|sp)\s*[:=\-]\s*(\d+)", r"^(1|2|3|5|8|13|21)$"]
        for text in labels + [issue.get("body") or ""]:
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    return int(match.group(1))
        return int(default_points)

    def chart_data(self):
        days = max(1, self.safe_int(self.sprint_days.get(), 10))
        goal = max(1, self.safe_int(self.sprint_goal.get(), 30))
        completed_by_day = [0] * (days + 1)
        for story in self.filtered_stories():
            if story.is_completed:
                day = min(days, max(1, story.completed_day or 1))
                completed_by_day[day] += story.points
        cumulative = []
        running = 0
        for day in range(days + 1):
            running += completed_by_day[day]
            cumulative.append(running)
        remaining = [max(0, goal - value) for value in cumulative]
        ideal_down = [goal * (1 - day / days) for day in range(days + 1)]
        ideal_up = [goal * day / days for day in range(days + 1)]
        return days, goal, cumulative, remaining, ideal_up, ideal_down

    def draw_charts(self):
        canvas = self.chart_canvas
        if not canvas.winfo_exists():
            return
        canvas.delete("all")
        width = max(800, canvas.winfo_width())
        height = max(500, canvas.winfo_height())
        days, goal, cumulative, remaining, ideal_up, ideal_down = self.chart_data()
        margin = 55
        gap = 60
        chart_w = (width - margin * 2 - gap) / 2
        chart_h = height - 120
        max_y = max(goal, max(cumulative, default=0), 1)

        def draw_one(x0, title, actual, ideal, actual_colour, y_label):
            y0 = 55
            x1 = x0 + chart_w
            y1 = y0 + chart_h
            canvas.create_text((x0 + x1) / 2, 22, text=title, font=("Times New Roman", 16, "bold"), fill="#153a5b")
            canvas.create_line(x0, y0, x0, y1, width=2, fill="#333333")
            canvas.create_line(x0, y1, x1, y1, width=2, fill="#333333")
            for i in range(6):
                value = max_y * i / 5
                py = y1 - chart_h * i / 5
                canvas.create_line(x0, py, x1, py, fill="#e5e5e5")
                canvas.create_text(x0 - 8, py, text=f"{value:.0f}", anchor="e", font=("Times New Roman", 9))
            step = max(1, days // 5)
            for day in range(0, days + 1, step):
                px = x0 + chart_w * day / days
                canvas.create_text(px, y1 + 16, text=str(day), font=("Times New Roman", 9))
            canvas.create_text((x0 + x1) / 2, y1 + 38, text="Sprint day", font=("Times New Roman", 11))
            canvas.create_text(x0 - 36, (y0 + y1) / 2, text=y_label, angle=90, font=("Times New Roman", 11))

            def points(values):
                result = []
                for day, value in enumerate(values):
                    px = x0 + chart_w * day / days
                    py = y1 - chart_h * value / max_y
                    result.extend((px, py))
                return result

            canvas.create_line(*points(ideal), fill="#777777", width=2, dash=(6, 4))
            canvas.create_line(*points(actual), fill=actual_colour, width=3)
            for p in range(0, len(points(actual)), 2):
                pts = points(actual)
                canvas.create_oval(pts[p]-3, pts[p+1]-3, pts[p]+3, pts[p+1]+3, fill=actual_colour, outline=actual_colour)
            canvas.create_line(x0 + 12, y0 + 10, x0 + 44, y0 + 10, fill=actual_colour, width=3)
            canvas.create_text(x0 + 48, y0 + 10, text="Actual", anchor="w", font=("Times New Roman", 9))
            canvas.create_line(x0 + 110, y0 + 10, x0 + 142, y0 + 10, fill="#777777", width=2, dash=(6, 4))
            canvas.create_text(x0 + 146, y0 + 10, text="Ideal", anchor="w", font=("Times New Roman", 9))

        draw_one(margin, "Burn-Up Chart", cumulative, ideal_up, "#2f7d4f", "Completed points")
        draw_one(margin + chart_w + gap, "Burn-Down Chart", remaining, ideal_down, "#b54c4c", "Remaining points")
        canvas.create_text(width / 2, height - 22,
                           text=f"{self.current_sprint.get()} • Goal: {goal} points • Completed: {cumulative[-1]} points • Only Completed stories counted",
                           font=("Times New Roman", 12, "bold"), fill="#153a5b")

    def export_charts(self):
        path = filedialog.asksaveasfilename(defaultextension=".ps", filetypes=[("PostScript", "*.ps")], initialfile="burn_charts.ps")
        if path:
            self.chart_canvas.postscript(file=path, colormode="color")
            self.status_message.set(f"Exported charts to {Path(path).name}.")


if __name__ == "__main__":
    app = AgileStudio()
    app.mainloop()
