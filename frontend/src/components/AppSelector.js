import React, { useState, useEffect } from 'react';
import './AppSelector.css';

const AppSelector = ({ onSourcesSelected, onClose }) => {
  const [sources, setSources] = useState([]);
  const [selectedSources, setSelectedSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all'); // 'all', 'windows', 'screens'

  useEffect(() => {
    loadSources();
  }, []);

  const loadSources = async () => {
    if (!window.electronAPI || !window.electronAPI.getCaptureSources) {
      setError('App selection is only available in the desktop app');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      const result = await window.electronAPI.getCaptureSources();
      
      if (result.success) {
        setSources(result.sources);
      } else {
        setError(result.error || 'Failed to get capture sources');
      }
    } catch (err) {
      setError(`Failed to load sources: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const toggleSource = (sourceId) => {
    setSelectedSources(prev => {
      if (prev.includes(sourceId)) {
        return prev.filter(id => id !== sourceId);
      } else {
        return [...prev, sourceId];
      }
    });
  };

  const handleConfirm = () => {
    const selected = sources.filter(source => selectedSources.includes(source.id));
    onSourcesSelected(selected);
    onClose();
  };

  // Group sources by application and filter out duplicate app windows
  const groupSourcesByApp = (sources) => {
    const appGroups = new Map();
    
    console.log('🔍 [AppSelector] Raw sources:', sources.map(s => ({ id: s.id, name: s.name, type: s.type })));
    
    sources.forEach(source => {
      if (source.type === 'screen') {
        // Keep all screens as-is
        appGroups.set(source.id, source);
        return;
      }
      
      // Extract app name from window title
      let appName = source.name;
      console.log(`🔍 [AppSelector] Processing window: "${source.name}"`);
      
      // Common patterns for extracting app names from window titles
      if (source.name.includes(' — Microsoft Teams')) {
        appName = 'Microsoft Teams';
      } else if (source.name.includes(' - Microsoft Teams')) {
        appName = 'Microsoft Teams';
      } else if (source.name.includes('MSTeams')) {
        // Handle "MSTeams - Teams Meeting" pattern
        appName = 'Microsoft Teams';
      } else if (source.name.includes('Chat |') && source.name.includes('|')) {
        // Handle "Chat | Memory & RAG discussion | A..." pattern (Teams chat windows)
        appName = 'Microsoft Teams';  
      } else if (source.name.includes(' — ')) {
        // For apps that use em dash separator (like many Mac apps)
        appName = source.name.split(' — ').pop();
      } else if (source.name.includes(' - ') && !source.name.startsWith('Untitled')) {
        // For apps that use regular dash separator, but exclude system windows
        const parts = source.name.split(' - ');
        if (parts.length > 1) {
          appName = parts[parts.length - 1];
        }
      }
      
      console.log(`🔍 [AppSelector] Extracted appName: "${appName}" from "${source.name}"`);
      
      // If we already have this app, prefer the main window over sub-windows
      const existingSource = appGroups.get(appName);
      
      if (!existingSource) {
        // First window for this app
        console.log(`🔍 [AppSelector] Adding new app: "${appName}"`);
        appGroups.set(appName, { ...source, appName });
      } else {
        console.log(`🔍 [AppSelector] Found duplicate app "${appName}": existing="${existingSource.name}", current="${source.name}"`);
        
        // Special handling for Microsoft Teams windows
        if (appName === 'Microsoft Teams') {
          const isCurrentMSTeams = source.name.includes('MSTeams');
          const isExistingMSTeams = existingSource.name.includes('MSTeams');
          const isCurrentChat = source.name.includes('Chat |');
          const isExistingChat = existingSource.name.includes('Chat |');
          
          console.log(`🔍 [AppSelector] Teams window check: current MSTeams=${isCurrentMSTeams}, current Chat=${isCurrentChat}, existing MSTeams=${isExistingMSTeams}, existing Chat=${isExistingChat}`);
          
          if (isCurrentMSTeams && !isExistingMSTeams) {
            // Current is MSTeams main window, prefer it over chat windows
            console.log(`🔍 [AppSelector] Replacing with MSTeams main window: "${source.name}"`);
            appGroups.set(appName, { ...source, appName });
          } else if (!isCurrentMSTeams && isExistingMSTeams) {
            // Existing is MSTeams main window, keep it
            console.log(`🔍 [AppSelector] Keeping existing MSTeams main window: "${existingSource.name}"`);
          } else if (isCurrentChat && !isExistingChat) {
            // Current is chat, existing is something else - prefer chat over generic
            console.log(`🔍 [AppSelector] Replacing with chat window: "${source.name}"`);
            appGroups.set(appName, { ...source, appName });
          } else {
            // Default: prefer shorter name
            if (source.name.length < existingSource.name.length) {
              console.log(`🔍 [AppSelector] Replacing with shorter Teams window: "${source.name}"`);
              appGroups.set(appName, { ...source, appName });
            } else {
              console.log(`🔍 [AppSelector] Keeping existing Teams window: "${existingSource.name}"`);
            }
          }
        } else {
          // Original logic for non-Teams apps
          const isCurrentMainWindow = source.name === appName || source.name.endsWith(appName);
          const isExistingMainWindow = existingSource.name === appName || existingSource.name.endsWith(appName);
          
          console.log(`🔍 [AppSelector] Main window check: current=${isCurrentMainWindow}, existing=${isExistingMainWindow}`);
          
          if (isCurrentMainWindow && !isExistingMainWindow) {
            // Current is main window, existing is sub-window - replace
            console.log(`🔍 [AppSelector] Replacing with main window: "${source.name}"`);
            appGroups.set(appName, { ...source, appName });
          } else if (!isCurrentMainWindow && !isExistingMainWindow) {
            // Both are sub-windows - prefer shorter name (usually more general)
            if (source.name.length < existingSource.name.length) {
              console.log(`🔍 [AppSelector] Replacing with shorter name: "${source.name}"`);
              appGroups.set(appName, { ...source, appName });
            } else {
              console.log(`🔍 [AppSelector] Keeping existing longer name: "${existingSource.name}"`);
            }
          } else {
            console.log(`🔍 [AppSelector] Keeping existing main window: "${existingSource.name}"`);
          }
        }
        // If existing is main window and current is sub-window, keep existing
      }
    });
    
    const result = Array.from(appGroups.values());
    console.log('🔍 [AppSelector] Final grouped sources:', result.map(s => ({ id: s.id, name: s.name, appName: s.appName })));
    return result;
  };

  const filteredSources = groupSourcesByApp(sources).filter(source => {
    if (filter === 'all') return true;
    if (filter === 'windows') return source.type === 'window';
    if (filter === 'screens') return source.type === 'screen';
    return true;
  });

  return (
    <div className="app-selector-overlay" onClick={onClose}>
      <div className="app-selector-modal" onClick={(e) => e.stopPropagation()}>
        <div className="app-selector-header">
          <h2>Select Apps to Monitor</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        {error && (
          <div className="app-selector-error">
            ⚠️ {error}
          </div>
        )}

        {loading ? (
          <div className="app-selector-loading">
            <div className="spinner"></div>
            <p>Scanning available apps and windows...</p>
            <p className="loading-note">This won't disturb your other applications</p>
          </div>
        ) : (
          <>
            <div className="app-selector-filters">
              <button 
                className={`filter-button ${filter === 'all' ? 'active' : ''}`}
                onClick={() => setFilter('all')}
              >
                All
              </button>
              <button 
                className={`filter-button ${filter === 'windows' ? 'active' : ''}`}
                onClick={() => setFilter('windows')}
              >
                Windows
              </button>
              <button 
                className={`filter-button ${filter === 'screens' ? 'active' : ''}`}
                onClick={() => setFilter('screens')}
              >
                Screens
              </button>
            </div>

            <div className="app-selector-grid">
              {filteredSources.map(source => (
                <div 
                  key={source.id}
                  className={`app-selector-item ${selectedSources.includes(source.id) ? 'selected' : ''}`}
                  onClick={() => toggleSource(source.id)}
                >
                  <div className="app-thumbnail">
                    <img src={source.thumbnail} alt={source.name} />
                    {selectedSources.includes(source.id) && (
                      <div className="selected-overlay">
                        <div className="checkmark">✓</div>
                      </div>
                    )}
                  </div>
                  <div className="app-info">
                    {source.appIcon && (
                      <img className="app-icon" src={source.appIcon} alt="" />
                    )}
                    <span className="app-name" title={source.name}>{source.name}</span>
                    <div className="app-badges">
                      <span className="app-type">{source.type}</span>
                      {source.isVirtual && !source.isVisible && (
                        <span className="app-status" title="This window is minimized or on another desktop">
                          Hidden
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="app-selector-footer">
              <div className="selection-info">
                {selectedSources.length} source{selectedSources.length !== 1 ? 's' : ''} selected
              </div>
              <div className="action-buttons">
                <button className="cancel-button" onClick={onClose}>
                  Cancel
                </button>
                <button 
                  className="confirm-button" 
                  onClick={handleConfirm}
                  disabled={selectedSources.length === 0}
                >
                  Start Monitoring
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default AppSelector;