import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useDropzone } from 'react-dropzone'
import { getProfile, updateSheetId, processInvoice, getUsage } from '../lib/api'
import './Dashboard.css'

const Dashboard = () => {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const [profile, setProfile] = useState(null)
  const [usage, setUsage] = useState(null)
  const [sheetId, setSheetId] = useState('')
  const [loading, setLoading] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [message, setMessage] = useState({ type: '', text: '' })

  const handleSignOut = async () => {
    try {
      await signOut()
      navigate('/login')
    } catch (error) {
      console.error('Error signing out:', error)
    }
  }

  useEffect(() => {
    loadProfile()
    loadUsage()
  }, [])

  const loadProfile = async () => {
    try {
      const response = await getProfile()
      setProfile(response.data)
      setSheetId(response.data.target_sheet_id || '')
    } catch (error) {
      console.error('Error loading profile:', error)
      setMessage({ type: 'error', text: 'Failed to load profile' })
    }
  }

  const loadUsage = async () => {
    try {
      const response = await getUsage()
      setUsage(response.data)
    } catch (error) {
      console.error('Error loading usage:', error)
    }
  }

  const handleSaveSheetId = async () => {
    if (!sheetId.trim()) {
      setMessage({ type: 'error', text: 'Please enter a Sheet ID' })
      return
    }

    setLoading(true)
    try {
      // Accept either full URL or raw ID
      const trimmed = sheetId.trim()
      const match = trimmed.match(/\/spreadsheets\/d\/([a-zA-Z0-9_-]+)/)
      const normalized = match?.[1] || trimmed
      setSheetId(normalized)
      await updateSheetId(normalized)
      setMessage({ type: 'success', text: 'Sheet ID saved successfully!' })
      loadProfile()
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Failed to save Sheet ID' })
    } finally {
      setLoading(false)
    }
  }

  const onDrop = async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return

    const file = acceptedFiles[0]
    
    if (!profile?.target_sheet_id) {
      setMessage({ type: 'error', text: 'Please configure your Target Sheet ID first' })
      return
    }

    setProcessing(true)
    setMessage({ type: 'info', text: 'Processing invoice...' })

    try {
      const response = await processInvoice(file)
      setMessage({ 
        type: 'success', 
        text: `Invoice processed successfully! Processed in ${response.data.processing_time_ms}ms` 
      })
      loadUsage()
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Failed to process invoice'
      setMessage({ type: 'error', text: errorMsg })
    } finally {
      setProcessing(false)
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg'],
      'application/pdf': ['.pdf']
    },
    disabled: processing || !profile?.target_sheet_id
  })

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="container">
          <div className="header-content">
            <div className="header-logo-section">
              <img src="/logo.svg" alt="Logo" className="header-logo" />
              <h1>InvoiceToSheet AI</h1>
            </div>
            <div className="header-actions">
              <div className="user-info">
                <span className="user-avatar">{user?.email?.charAt(0).toUpperCase()}</span>
                <span className="user-email">{user?.email}</span>
              </div>
              <button className="btn btn-danger" onClick={handleSignOut}>Déconnexion</button>
            </div>
          </div>
        </div>
      </header>

      <main className="container">
        {message.text && (
          <div className={`alert alert-${message.type}`}>
            {message.text}
          </div>
        )}

        <div className="card">
          <h2 className="card-title">
            <svg className="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            Configuration
          </h2>
          <div className="form-group">
            <label className="form-label">ID Google Sheet cible</label>
            <input
              type="text"
              className="form-input"
              placeholder="Entrez votre Google Sheet ID"
              value={sheetId}
              onChange={(e) => setSheetId(e.target.value)}
              disabled={loading}
            />
            <small className="form-help">
              Trouvez-le dans l'URL de votre Google Sheet : docs.google.com/spreadsheets/d/[SHEET_ID]/edit
            </small>
          </div>
          <button 
            className="btn btn-primary" 
            onClick={handleSaveSheetId}
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="loading"></span>
                Enregistrement...
              </>
            ) : (
              <>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                  <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                  <polyline points="17 21 17 13 7 13 7 21"></polyline>
                  <polyline points="7 3 7 8 15 8"></polyline>
                </svg>
                Enregistrer l'ID Sheet
              </>
            )}
          </button>
        </div>

        {usage && (
          <div className="card">
            <h2 className="card-title">
              <svg className="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="20" x2="12" y2="10"></line>
                <line x1="18" y1="20" x2="18" y2="4"></line>
                <line x1="6" y1="20" x2="6" y2="16"></line>
              </svg>
              Statistiques d'utilisation
            </h2>
            <div className="usage-stats">
              <div className="stat-item">
                <div className="stat-icon stat-icon-primary">📊</div>
                <span className="stat-label">Limite mensuelle</span>
                <span className="stat-value">{usage.monthly_limit}</span>
              </div>
              <div className="stat-item">
                <div className="stat-icon stat-icon-success">✅</div>
                <span className="stat-label">Utilisé ce mois</span>
                <span className="stat-value">{usage.current_usage}</span>
              </div>
              <div className="stat-item">
                <div className="stat-icon stat-icon-info">📈</div>
                <span className="stat-label">Restant</span>
                <span className="stat-value">{usage.remaining}</span>
              </div>
              <div className="stat-item">
                <div className="stat-icon stat-icon-warning">⚠️</div>
                <span className="stat-label">Échecs</span>
                <span className="stat-value">{usage.failed}</span>
              </div>
            </div>
          </div>
        )}

        <div className="card">
          <h2 className="card-title">
            <svg className="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            Télécharger une facture
          </h2>
          <p className="card-subtitle">
            Glissez-déposez un fichier de facture ici, ou cliquez pour sélectionner
          </p>
          <div
            {...getRootProps()}
            className={`dropzone ${isDragActive ? 'dropzone-active' : ''} ${processing ? 'dropzone-disabled' : ''}`}
          >
            <input {...getInputProps()} />
            {processing ? (
              <div className="dropzone-content">
                <div className="loading"></div>
                <p className="dropzone-text">Traitement de la facture en cours...</p>
              </div>
            ) : isDragActive ? (
              <div className="dropzone-content">
                <svg className="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="64" height="64">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="17 8 12 3 7 8"></polyline>
                  <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
                <p className="dropzone-text">Déposez le fichier ici...</p>
              </div>
            ) : (
              <div className="dropzone-content">
                <svg className="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="64" height="64">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="7 10 12 15 17 10"></polyline>
                  <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                <p className="dropzone-text">
                  <strong>Cliquez pour télécharger</strong> ou glissez-déposez
                </p>
                <p className="dropzone-hint">PNG, JPG, PDF jusqu'à 10MB</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

export default Dashboard
