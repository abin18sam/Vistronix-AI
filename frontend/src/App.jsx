import './App.css'

const features = [
  {
    title: 'AI understanding',
    description: 'Transforms dense chapters into clear concepts, summaries, and learning structure.',
  },
  {
    title: 'Visual storytelling',
    description: 'Builds scenes, visuals, and chapter flow into a narrative learning experience.',
  },
  {
    title: 'Narrated lessons',
    description: 'Generates voice-over, captions, and cinematic pacing for easier retention.',
  },
]

const workflowSteps = [
  'Upload your PDF or study material',
  'Extract and understand the document content',
  'Build concepts, scenes, and knowledge graph',
  'Render a learning video with narration',
]

const projectCards = [
  { name: 'Operating Systems', type: 'CS', duration: '14:32', accent: 'cyan' },
  { name: 'DBMS', type: 'Database', duration: '08:41', accent: 'purple' },
  { name: 'Machine Learning', type: 'AI', duration: '12:18', accent: 'violet' },
]

function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-wrap">
          <div className="brand-mark">V</div>
          <span className="brand-name">VisTronix</span>
        </div>

        <nav className="topnav" aria-label="Main navigation">
          <a href="#features">Features</a>
          <a href="#how-it-works">How it works</a>
          <a href="#projects">Projects</a>
        </nav>

        <button type="button" className="nav-button">
          Sign in
        </button>
      </header>

      <main className="page">
        <section className="hero section-card">
          <div className="hero-copy">
            <span className="eyebrow">AI education engine</span>
            <h1>Turn knowledge into visual learning.</h1>
            <p>
              Upload PDFs, lecture notes, or textbooks and turn them into structured lessons with
              narration, scenes, and understanding designed for faster learning.
            </p>

            <div className="cta-row">
              <button type="button" className="primary-button">
                Create your first video
              </button>
              <button type="button" className="secondary-button">
                Watch demo
              </button>
            </div>

            <div className="mini-metrics">
              <div>
                <strong>200+</strong>
                <span>concepts mapped</span>
              </div>
              <div>
                <strong>4x</strong>
                <span>faster learning loops</span>
              </div>
            </div>
          </div>

          <div className="hero-preview" aria-label="Lesson generation preview">
            <div className="preview-window">
              <div className="preview-topbar">
                <span className="dot red" />
                <span className="dot amber" />
                <span className="dot green" />
              </div>

              <div className="preview-body">
                <div className="file-badge">PDF</div>
                <h3>Operating Systems</h3>
                <div className="preview-meta">
                  <span>23.4 MB</span>
                  <span>146 concepts</span>
                </div>

                <div className="pipeline">
                  <span className="done">Extracted</span>
                  <span className="done">Understood</span>
                  <span className="active">Generating scenes</span>
                </div>

                <div className="progress-bar">
                  <span />
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="stats-row">
          <div className="stat-box">
            <span className="stat-label">Documents processed</span>
            <strong>1.2K</strong>
          </div>
          <div className="stat-box">
            <span className="stat-label">Video lessons created</span>
            <strong>780</strong>
          </div>
          <div className="stat-box">
            <span className="stat-label">Avg. comprehension lift</span>
            <strong>+46%</strong>
          </div>
        </section>

        <section className="workspace-panel" id="projects">
          <aside className="sidebar">
            <div className="sidebar-header">Workspace</div>
            <ul>
              <li className="active">Dashboard</li>
              <li>Projects</li>
              <li>Templates</li>
              <li>Videos</li>
              <li>Settings</li>
            </ul>
          </aside>

          <div className="workspace-content">
            <div className="panel-header">
              <div>
                <p className="muted">Good morning, Abin</p>
                <h2>Build your next lesson</h2>
              </div>
              <button type="button" className="secondary-button small-button">
                New project
              </button>
            </div>

            <div className="upload-box">
              <div className="upload-icon">📄</div>
              <h3>Drop your PDF here</h3>
              <p>or browse files from your device</p>
              <button type="button" className="primary-button small-button">
                Browse Files
              </button>
            </div>

            <div className="recent-projects">
              <div className="projects-title-row">
                <h3>Recent projects</h3>
                <a href="#">View all</a>
              </div>

              <div className="project-grid">
                {projectCards.map((project) => (
                  <article key={project.name} className={`project-card ${project.accent}`}>
                    <div className="project-icon">◉</div>
                    <div className="project-info">
                      <h4>{project.name}</h4>
                      <span>{project.type}</span>
                    </div>
                    <strong>{project.duration}</strong>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="feature-section" id="features">
          <div className="section-heading">
            <span className="eyebrow">Why VisTronix</span>
            <h2>Made for learning, not just summarizing.</h2>
          </div>

          <div className="feature-grid">
            {features.map((feature) => (
              <article key={feature.title} className="feature-card">
                <div className="feature-icon">✦</div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="process-section" id="how-it-works">
          <div className="section-heading">
            <span className="eyebrow">How it works</span>
            <h2>From uploaded material to visual lesson.</h2>
          </div>

          <div className="steps-grid">
            {workflowSteps.map((step, index) => (
              <div key={step} className="step-card">
                <span className="step-number">0{index + 1}</span>
                <p>{step}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  )
}

export default App
