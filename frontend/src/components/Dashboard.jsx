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
      await updateSheetId(sheetId.trim())
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
            <h1>InvoiceToSheet AI</h1>
            <div className="header-actions">
              <span className="user-email">{user?.email}</span>
              <button className="btn btn-danger" onClick={handleSignOut}>Sign Out</button>
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
          <h2 className="card-title">Configuration</h2>
          <div className="form-group">
            <label className="form-label">Target Google Sheet ID</label>
            <input
              type="text"
              className="form-input"
              placeholder="Enter your Google Sheet ID"
              value={sheetId}
              onChange={(e) => setSheetId(e.target.value)}
              disabled={loading}
            />
            <small className="form-help">
              Find this in your Google Sheet URL: docs.google.com/spreadsheets/d/[SHEET_ID]/edit
            </small>
          </div>
          <button 
            className="btn btn-primary" 
            onClick={handleSaveSheetId}
            disabled={loading}
          >
            {loading ? 'Saving...' : 'Save Sheet ID'}
          </button>
        </div>

        {usage && (
          <div className="card">
            <h2 className="card-title">Usage Statistics</h2>
            <div className="usage-stats">
              <div className="stat-item">
                <span className="stat-label">Monthly Limit:</span>
                <span className="stat-value">{usage.monthly_limit}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Used This Month:</span>
                <span className="stat-value">{usage.current_usage}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Remaining:</span>
                <span className="stat-value">{usage.remaining}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Failed:</span>
                <span className="stat-value">{usage.failed}</span>
              </div>
            </div>
          </div>
        )}

        <div className="card">
          <h2 className="card-title">Upload Invoice</h2>
          <p className="card-subtitle">
            Drag and drop an invoice file here, or click to select
          </p>
          <div
            {...getRootProps()}
            className={`dropzone ${isDragActive ? 'dropzone-active' : ''} ${processing ? 'dropzone-disabled' : ''}`}
          >
            <input {...getInputProps()} />
            {processing ? (
              <div>
                <div className="loading"></div>
                <p>Processing invoice...</p>
              </div>
            ) : isDragActive ? (
              <p>Drop the invoice file here...</p>
            ) : (
              <div>
                <p className="dropzone-text">
                  <strong>Click to upload</strong> or drag and drop
                </p>
                <p className="dropzone-hint">PNG, JPG, PDF up to 10MB</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

export default Dashboard
