import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from 'chart.js';
import { Bar, Line, Doughnut } from 'react-chartjs-2';
import Editor from '@monaco-editor/react';
import './App.css';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
);

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Role requirements for upgrade planning
const ROLE_REQUIREMENTS = {
  'Quantum Software Engineer': ['Qiskit', 'Python', 'Quantum Algorithms', 'Linear Algebra'],
  'Quantum Research Scientist': ['Quantum Physics', 'Research Methods', 'Python', 'Mathematics'],
  'Quantum Hardware Engineer': ['Electronics', 'Physics', 'Hardware Design', 'Quantum Systems'],
  'Quantum Algorithm Developer': ['Algorithm Design', 'Quantum Computing', 'Python', 'Mathematics'],
  'Quantum Data Scientist': ['Data Science', 'Python', 'Quantum ML', 'Statistics']
};

function App() {
  const [activeTab, setActiveTab] = useState('upload');
  const [userId] = useState(() => `user_${Date.now()}`);
  const [resumeData, setResumeData] = useState(null);
  const [jobRecommendations, setJobRecommendations] = useState(null);
  const [testSession, setTestSession] = useState(null);
  const [testHistory, setTestHistory] = useState(null);
  const [upgradeData, setUpgradeData] = useState(null);
  const [profileOverview, setProfileOverview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Test-related states
  const [testAnswers, setTestAnswers] = useState({});
  const [codingAnswers, setCodingAnswers] = useState({});
  const [testStarted, setTestStarted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [testResults, setTestResults] = useState(null);
  const [timeLeft, setTimeLeft] = useState(0);
  
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (activeTab === 'profile') {
      fetchProfileOverview();
    }
  }, [activeTab]);

  // Test timer
  useEffect(() => {
    let interval = null;
    if (testStarted && timeLeft > 0) {
      interval = setInterval(() => {
        setTimeLeft(timeLeft => timeLeft - 1);
      }, 1000);
    } else if (timeLeft === 0 && testStarted) {
      handleSubmitTest();
    }
    return () => clearInterval(interval);
  }, [testStarted, timeLeft]);

  // Fullscreen detection
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // Focus detection for test
  useEffect(() => {
    if (testStarted && !testResults) {
      const handleVisibilityChange = () => {
        if (document.hidden) {
          alert('⚠️ Tab switching detected! Please stay focused on the test.');
        }
      };

      const handleFocus = () => {
        if (!document.hasFocus()) {
          alert('⚠️ Please keep focus on the test window!');
        }
      };

      document.addEventListener('visibilitychange', handleVisibilityChange);
      window.addEventListener('blur', handleFocus);

      return () => {
        document.removeEventListener('visibilitychange', handleVisibilityChange);
        window.removeEventListener('blur', handleFocus);
      };
    }
  }, [testStarted, testResults]);

  const showMessage = (msg, isError = false) => {
    if (isError) {
      setError(msg);
      setSuccess('');
    } else {
      setSuccess(msg);
      setError('');
    }
    setTimeout(() => {
      setError('');
      setSuccess('');
    }, 5000);
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', userId);

      const response = await axios.post(`${API_BASE_URL}/api/upload_resume`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setResumeData(response.data);
      showMessage('Resume uploaded and analyzed successfully!');
      
      // Also fetch job recommendations
      await fetchJobRecommendations();
    } catch (error) {
      showMessage(`Error uploading resume: ${error.response?.data?.detail || error.message}`, true);
    } finally {
      setLoading(false);
    }
  };

  const fetchJobRecommendations = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/get_job_recommendations/${userId}`);
      setJobRecommendations(response.data);
    } catch (error) {
      console.error('Error fetching job recommendations:', error);
    }
  };

  const startTest = async () => {
    if (!isFullscreen) {
      try {
        await document.documentElement.requestFullscreen();
      } catch (error) {
        showMessage('Please enable fullscreen mode to start the test', true);
        return;
      }
    }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('user_id', userId);

      const response = await axios.post(`${API_BASE_URL}/api/start_test`, formData);
      setTestSession(response.data);
      setTestStarted(true);
      setTimeLeft(response.data.duration_minutes * 60); // Convert to seconds
      showMessage('Test started! Good luck!');
    } catch (error) {
      showMessage(`Error starting test: ${error.response?.data?.detail || error.message}`, true);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitTest = async () => {
    if (!testSession) return;

    setLoading(true);
    try {
      const submission = {
        session_id: testSession.session_id,
        mcq_answers: testAnswers,
        coding_answers: codingAnswers,
      };

      const response = await axios.post(`${API_BASE_URL}/api/submit_test`, submission);
      setTestResults(response.data);
      setTestStarted(false);
      showMessage('Test submitted successfully!');
      
      if (document.fullscreenElement) {
        document.exitFullscreen();
      }
    } catch (error) {
      showMessage(`Error submitting test: ${error.response?.data?.detail || error.message}`, true);
    } finally {
      setLoading(false);
    }
  };

  const fetchTestHistory = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/api/get_test_history/${userId}`);
      setTestHistory(response.data);
    } catch (error) {
      showMessage(`Error fetching test history: ${error.response?.data?.detail || error.message}`, true);
    } finally {
      setLoading(false);
    }
  };

  const fetchUpgradePlan = async (targetRole) => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('target_role', targetRole);
      formData.append('user_id', userId);

      const response = await axios.post(`${API_BASE_URL}/api/upgrade_me`, formData);
      setUpgradeData(response.data);
      showMessage('Upgrade plan generated!');
    } catch (error) {
      showMessage(`Error generating upgrade plan: ${error.response?.data?.detail || error.message}`, true);
    } finally {
      setLoading(false);
    }
  };

  const fetchProfileOverview = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/profile_overview/${userId}`);
      setProfileOverview(response.data);
    } catch (error) {
      console.error('Error fetching profile overview:', error);
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const renderTechStackChart = () => {
    if (!resumeData?.tech_stacks) return null;

    const data = {
      labels: resumeData.tech_stacks,
      datasets: [
        {
          label: 'Skills Found',
          data: resumeData.tech_stacks.map(() => 1),
          backgroundColor: 'rgba(99, 102, 241, 0.6)',
          borderColor: 'rgba(99, 102, 241, 1)',
          borderWidth: 1,
        },
      ],
    };

    const options = {
      responsive: true,
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#e5e7eb' }
        },
        title: {
          display: true,
          text: 'Technology Skills Detected',
          color: '#e5e7eb'
        },
      },
      scales: {
        y: {
          ticks: { color: '#e5e7eb' },
          grid: { color: 'rgba(229, 231, 235, 0.1)' }
        },
        x: {
          ticks: { color: '#e5e7eb' },
          grid: { color: 'rgba(229, 231, 235, 0.1)' }
        }
      },
    };

    return <Bar data={data} options={options} />;
  };

  const renderStrengthGauge = () => {
    if (!resumeData?.strength_score) return null;

    const score = resumeData.strength_score;
    const data = {
      labels: ['Score', 'Remaining'],
      datasets: [
        {
          data: [score, 10 - score],
          backgroundColor: [
            score >= 8 ? '#10B981' : score >= 6 ? '#F59E0B' : '#EF4444',
            'rgba(75, 85, 99, 0.3)',
          ],
          borderWidth: 0,
        },
      ],
    };

    const options = {
      responsive: true,
      cutout: '70%',
      plugins: {
        legend: { display: false },
        title: {
          display: true,
          text: `Resume Strength: ${score.toFixed(1)}/10`,
          color: '#e5e7eb'
        },
      },
    };

    return <Doughnut data={data} options={options} />;
  };

  const renderTestHistoryChart = () => {
    if (!testHistory?.test_history?.length) return null;

    const data = {
      labels: testHistory.test_history.map((_, index) => `Test ${index + 1}`),
      datasets: [
        {
          label: 'Test Scores',
          data: testHistory.test_history.map(test => test.total_score),
          borderColor: 'rgb(99, 102, 241)',
          backgroundColor: 'rgba(99, 102, 241, 0.2)',
          tension: 0.1,
        },
      ],
    };

    const options = {
      responsive: true,
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#e5e7eb' }
        },
        title: {
          display: true,
          text: 'Test Performance Over Time',
          color: '#e5e7eb'
        },
      },
      scales: {
        y: {
          ticks: { color: '#e5e7eb' },
          grid: { color: 'rgba(229, 231, 235, 0.1)' },
          min: 0,
          max: 100
        },
        x: {
          ticks: { color: '#e5e7eb' },
          grid: { color: 'rgba(229, 231, 235, 0.1)' }
        }
      },
    };

    return <Line data={data} options={options} />;
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-800 shadow-lg">
        <div className="container mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-center bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            IBM Quantum Jobs Tracker - User Analytics
          </h1>
        </div>
      </header>

      {/* Messages */}
      {(error || success) && (
        <div className={`fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg ${error ? 'bg-red-600' : 'bg-green-600'}`}>
          {error || success}
        </div>
      )}

      {/* Loading Overlay */}
      {loading && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-40">
          <div className="bg-gray-800 p-6 rounded-lg">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
            <p className="mt-4 text-center">Processing...</p>
          </div>
        </div>
      )}

      {/* Navigation */}
      <nav className="bg-gray-800 border-b border-gray-700">
        <div className="container mx-auto px-4">
          <div className="flex space-x-1">
            {[
              { id: 'upload', label: 'Resume Upload', icon: '📄' },
              { id: 'analysis', label: 'Analysis', icon: '📊' },
              { id: 'jobs', label: 'Job Recommendations', icon: '💼' },
              { id: 'test', label: 'Take Test', icon: '🧪' },
              { id: 'history', label: 'Test History', icon: '📈' },
              { id: 'upgrade', label: 'Upgrade Me', icon: '🚀' },
              { id: 'profile', label: 'Profile Overview', icon: '👤' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-3 text-sm font-medium rounded-t-lg transition-colors ${
                  activeTab === tab.id
                    ? 'bg-gray-700 text-blue-400 border-b-2 border-blue-400'
                    : 'text-gray-400 hover:text-white hover:bg-gray-700'
                }`}
              >
                <span className="mr-2">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        {/* Resume Upload Tab */}
        {activeTab === 'upload' && (
          <div className="max-w-2xl mx-auto">
            <div className="bg-gray-800 rounded-lg p-8 shadow-xl">
              <h2 className="text-2xl font-bold mb-6 text-center">Upload Your Resume</h2>
              <div className="border-2 border-dashed border-gray-600 rounded-lg p-8 text-center hover:border-blue-500 transition-colors">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  accept=".pdf,.docx"
                  className="hidden"
                />
                <div className="text-6xl mb-4">📄</div>
                <p className="text-lg mb-4">Drag & drop your resume here, or click to browse</p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-medium transition-colors"
                >
                  Choose File
                </button>
                <p className="text-sm text-gray-400 mt-4">
                  Supported formats: PDF, DOCX (Max 10MB)
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Analysis Tab */}
        {activeTab === 'analysis' && (
          <div className="space-y-8">
            {resumeData ? (
              <>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  <div className="bg-gray-800 rounded-lg p-6">
                    <h3 className="text-xl font-bold mb-4">Technology Skills</h3>
                    <div className="h-64">
                      {renderTechStackChart()}
                    </div>
                  </div>
                  
                  <div className="bg-gray-800 rounded-lg p-6">
                    <h3 className="text-xl font-bold mb-4">Resume Strength</h3>
                    <div className="h-64 flex items-center justify-center">
                      {renderStrengthGauge()}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  <div className="bg-gray-800 rounded-lg p-6">
                    <h3 className="text-xl font-bold mb-4">Education</h3>
                    <div className="space-y-3">
                      {resumeData.education?.length > 0 ? (
                        resumeData.education.map((edu, index) => (
                          <div key={index} className="bg-gray-700 p-3 rounded">
                            <p>{edu.description}</p>
                            {edu.year && <p className="text-sm text-gray-400">Year: {edu.year}</p>}
                          </div>
                        ))
                      ) : (
                        <p className="text-gray-400">No education information detected</p>
                      )}
                    </div>
                  </div>

                  <div className="bg-gray-800 rounded-lg p-6">
                    <h3 className="text-xl font-bold mb-4">Work Experience</h3>
                    <div className="space-y-3">
                      {resumeData.work_experience?.length > 0 ? (
                        resumeData.work_experience.map((exp, index) => (
                          <div key={index} className="bg-gray-700 p-3 rounded">
                            <p>{exp.role}</p>
                            {exp.year && <p className="text-sm text-gray-400">Year: {exp.year}</p>}
                            {exp.duration && <p className="text-sm text-gray-400">Duration: {exp.duration} years</p>}
                          </div>
                        ))
                      ) : (
                        <p className="text-gray-400">No work experience detected</p>
                      )}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-12">
                <p className="text-xl text-gray-400">Please upload your resume first to see the analysis</p>
              </div>
            )}
          </div>
        )}

        {/* Job Recommendations Tab */}
        {activeTab === 'jobs' && (
          <div className="space-y-6">
            {jobRecommendations ? (
              <>
                <h2 className="text-2xl font-bold text-center mb-8">Recommended Quantum Jobs</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {jobRecommendations.recommendations.map((job) => (
                    <div key={job.job_id} className="bg-gray-800 rounded-lg p-6 hover:bg-gray-750 transition-colors">
                      <div className="flex justify-between items-start mb-4">
                        <h3 className="text-xl font-bold">{job.title}</h3>
                        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                          job.match_percentage >= 70 ? 'bg-green-600' : 
                          job.match_percentage >= 40 ? 'bg-yellow-600' : 'bg-red-600'
                        }`}>
                          {job.match_percentage.toFixed(0)}% Match
                        </span>
                      </div>
                      
                      <p className="text-blue-400 mb-3">{job.company}</p>
                      
                      <div className="mb-4">
                        <h4 className="font-medium mb-2">Matching Skills:</h4>
                        <div className="flex flex-wrap gap-1">
                          {job.matching_skills.map((skill, index) => (
                            <span key={index} className="px-2 py-1 bg-green-600 text-xs rounded">
                              {skill}
                            </span>
                          ))}
                        </div>
                      </div>

                      {job.missing_skills.length > 0 && (
                        <div className="mb-4">
                          <h4 className="font-medium mb-2">Skills to Learn:</h4>
                          <div className="flex flex-wrap gap-1">
                            {job.missing_skills.map((skill, index) => (
                              <span key={index} className="px-2 py-1 bg-red-600 text-xs rounded">
                                {skill}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      <button className="w-full bg-blue-600 hover:bg-blue-700 py-2 rounded font-medium transition-colors">
                        Apply Now
                      </button>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="text-center py-12">
                <p className="text-xl text-gray-400">Please upload your resume first to see job recommendations</p>
              </div>
            )}
          </div>
        )}

        {/* Test Tab */}
        {activeTab === 'test' && (
          <div className="max-w-4xl mx-auto">
            {!testStarted && !testResults && (
              <div className="bg-gray-800 rounded-lg p-8 text-center">
                <h2 className="text-2xl font-bold mb-6">Skills Assessment Test</h2>
                <div className="mb-6">
                  <p className="text-lg mb-4">Test includes:</p>
                  <ul className="text-left max-w-md mx-auto space-y-2">
                    <li>• Multiple Choice Questions (Quantum Computing Basics)</li>
                    <li>• Coding Challenges (Python/Algorithm)</li>
                    <li>• 30 minutes duration</li>
                    <li>• Full-screen mode required</li>
                  </ul>
                </div>
                <button
                  onClick={startTest}
                  className="bg-green-600 hover:bg-green-700 px-8 py-3 rounded-lg font-medium text-lg transition-colors"
                >
                  Start Test
                </button>
              </div>
            )}

            {testStarted && testSession && (
              <div className="space-y-6">
                <div className="bg-gray-800 rounded-lg p-4 flex justify-between items-center">
                  <h2 className="text-xl font-bold">Skills Assessment Test</h2>
                  <div className="flex items-center space-x-4">
                    <span className={`text-lg font-mono ${timeLeft < 300 ? 'text-red-400' : 'text-green-400'}`}>
                      ⏱️ {formatTime(timeLeft)}
                    </span>
                    <span className={`px-3 py-1 rounded-full text-sm ${isFullscreen ? 'bg-green-600' : 'bg-red-600'}`}>
                      {isFullscreen ? 'Fullscreen ✓' : 'Fullscreen ✗'}
                    </span>
                  </div>
                </div>

                {/* MCQ Section */}
                <div className="bg-gray-800 rounded-lg p-6">
                  <h3 className="text-xl font-bold mb-6">Multiple Choice Questions</h3>
                  {testSession.mcq_questions.map((question, index) => (
                    <div key={question.id} className="mb-8 p-4 bg-gray-700 rounded-lg">
                      <h4 className="font-medium mb-4">
                        {index + 1}. {question.question}
                      </h4>
                      <div className="space-y-2">
                        {question.options.map((option, optionIndex) => (
                          <label key={optionIndex} className="flex items-center cursor-pointer hover:bg-gray-600 p-2 rounded">
                            <input
                              type="radio"
                              name={question.id}
                              value={optionIndex}
                              onChange={(e) => setTestAnswers({
                                ...testAnswers,
                                [question.id]: parseInt(e.target.value)
                              })}
                              className="mr-3"
                            />
                            <span>{option}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Coding Section */}
                <div className="bg-gray-800 rounded-lg p-6">
                  <h3 className="text-xl font-bold mb-6">Coding Questions</h3>
                  {testSession.coding_questions.map((question, index) => (
                    <div key={question.id} className="mb-8">
                      <h4 className="font-medium mb-4">
                        {index + 1}. {question.question}
                      </h4>
                      <div className="bg-gray-900 rounded-lg overflow-hidden">
                        <Editor
                          height="300px"
                          defaultLanguage="python"
                          defaultValue={question.template}
                          theme="vs-dark"
                          onChange={(value) => setCodingAnswers({
                            ...codingAnswers,
                            [question.id]: value || ''
                          })}
                          options={{
                            minimap: { enabled: false },
                            fontSize: 14,
                            scrollBeyondLastLine: false,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>

                <div className="text-center">
                  <button
                    onClick={handleSubmitTest}
                    className="bg-blue-600 hover:bg-blue-700 px-8 py-3 rounded-lg font-medium text-lg transition-colors"
                  >
                    Submit Test
                  </button>
                </div>
              </div>
            )}

            {testResults && (
              <div className="bg-gray-800 rounded-lg p-8">
                <h2 className="text-2xl font-bold text-center mb-6">Test Results</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                  <div className="text-center p-6 bg-gray-700 rounded-lg">
                    <h3 className="text-lg font-medium mb-2">Total Score</h3>
                    <p className="text-3xl font-bold text-blue-400">{testResults.total_score.toFixed(1)}%</p>
                  </div>
                  <div className="text-center p-6 bg-gray-700 rounded-lg">
                    <h3 className="text-lg font-medium mb-2">MCQ Score</h3>
                    <p className="text-3xl font-bold text-green-400">{testResults.mcq_results.score.toFixed(1)}%</p>
                    <p className="text-sm text-gray-400">{testResults.mcq_results.correct}/{testResults.mcq_results.total} correct</p>
                  </div>
                  <div className="text-center p-6 bg-gray-700 rounded-lg">
                    <h3 className="text-lg font-medium mb-2">Coding Score</h3>
                    <p className="text-3xl font-bold text-purple-400">{testResults.coding_results.score.toFixed(1)}%</p>
                  </div>
                </div>
                
                <div className="text-center">
                  <button
                    onClick={() => {
                      setTestResults(null);
                      setTestSession(null);
                      setTestAnswers({});
                      setCodingAnswers({});
                    }}
                    className="bg-green-600 hover:bg-green-700 px-6 py-2 rounded-lg font-medium transition-colors mr-4"
                  >
                    Take Another Test
                  </button>
                  <button
                    onClick={() => setActiveTab('history')}
                    className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-lg font-medium transition-colors"
                  >
                    View Test History
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Test History Tab */}
        {activeTab === 'history' && (
          <div className="space-y-8">
            <div className="text-center">
              <button
                onClick={fetchTestHistory}
                className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-medium transition-colors"
              >
                Load Test History
              </button>
            </div>

            {testHistory && (
              <>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                  <div className="bg-gray-800 rounded-lg p-6 text-center">
                    <h3 className="text-lg font-medium mb-2">Total Tests</h3>
                    <p className="text-3xl font-bold text-blue-400">{testHistory.analytics.total_tests}</p>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-6 text-center">
                    <h3 className="text-lg font-medium mb-2">Average Score</h3>
                    <p className="text-3xl font-bold text-green-400">{testHistory.analytics.average_score.toFixed(1)}%</p>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-6 text-center">
                    <h3 className="text-lg font-medium mb-2">Best Score</h3>
                    <p className="text-3xl font-bold text-purple-400">{testHistory.analytics.best_score.toFixed(1)}%</p>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-6 text-center">
                    <h3 className="text-lg font-medium mb-2">Trend</h3>
                    <p className="text-2xl">
                      {testHistory.analytics.improvement_trend === 'improving' ? '📈' : '📊'}
                    </p>
                  </div>
                </div>

                {testHistory.test_history.length > 0 && (
                  <div className="bg-gray-800 rounded-lg p-6">
                    <h3 className="text-xl font-bold mb-4">Performance Chart</h3>
                    <div className="h-64">
                      {renderTestHistoryChart()}
                    </div>
                  </div>
                )}

                <div className="bg-gray-800 rounded-lg p-6">
                  <h3 className="text-xl font-bold mb-4">Recent Tests</h3>
                  <div className="space-y-4">
                    {testHistory.test_history.slice(0, 5).map((test, index) => (
                      <div key={index} className="flex justify-between items-center p-4 bg-gray-700 rounded-lg">
                        <div>
                          <p className="font-medium">Test #{testHistory.test_history.length - index}</p>
                          <p className="text-sm text-gray-400">
                            {new Date(test.timestamp).toLocaleDateString()}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-lg font-bold">{test.total_score.toFixed(1)}%</p>
                          <p className="text-sm text-gray-400">
                            MCQ: {test.mcq_results.score.toFixed(0)}% | 
                            Code: {test.coding_results.score.toFixed(0)}%
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* Upgrade Me Tab */}
        {activeTab === 'upgrade' && (
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="bg-gray-800 rounded-lg p-8">
              <h2 className="text-2xl font-bold text-center mb-6">Upgrade Your Skills</h2>
              <p className="text-center text-gray-400 mb-8">
                Select your target role to get a personalized upgrade plan
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                {Object.keys(ROLE_REQUIREMENTS).map((role) => (
                  <button
                    key={role}
                    onClick={() => fetchUpgradePlan(role)}
                    className="p-4 bg-gray-700 hover:bg-gray-600 rounded-lg text-left transition-colors"
                  >
                    <h3 className="font-bold mb-2">{role}</h3>
                    <p className="text-sm text-gray-400">
                      Get personalized learning path
                    </p>
                  </button>
                ))}
              </div>

              {upgradeData && (
                <div className="space-y-6">
                  <div className="border-t border-gray-700 pt-6">
                    <h3 className="text-xl font-bold mb-4">Upgrade Plan for {upgradeData.target_role}</h3>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="bg-gray-700 rounded-lg p-6">
                        <h4 className="font-bold mb-4 text-red-400">Skills to Learn</h4>
                        <div className="space-y-2">
                          {upgradeData.missing_skills.map((skill, index) => (
                            <div key={index} className="flex items-center">
                              <span className="w-2 h-2 bg-red-400 rounded-full mr-3"></span>
                              <span>{skill}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="bg-gray-700 rounded-lg p-6">
                        <h4 className="font-bold mb-4 text-blue-400">Estimated Timeline</h4>
                        <p className="text-2xl font-bold mb-2">{upgradeData.estimated_time_weeks} weeks</p>
                        <p className="text-gray-400">Based on 10-15 hours/week study time</p>
                      </div>
                    </div>

                    <div className="bg-gray-700 rounded-lg p-6 mt-6">
                      <h4 className="font-bold mb-4 text-green-400">Learning Resources</h4>
                      <div className="space-y-3">
                        {upgradeData.recommended_resources.map((resource, index) => (
                          <div key={index} className="flex justify-between items-center p-3 bg-gray-600 rounded">
                            <div>
                              <p className="font-medium">{resource.resource_name}</p>
                              <p className="text-sm text-gray-400">{resource.skill} • {resource.duration}</p>
                            </div>
                            <button className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded text-sm transition-colors">
                              Start Learning
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="bg-gray-700 rounded-lg p-6 mt-6">
                      <h4 className="font-bold mb-4 text-purple-400">Suggested Projects</h4>
                      <div className="space-y-2">
                        {upgradeData.suggested_projects.map((project, index) => (
                          <div key={index} className="flex items-center">
                            <span className="w-2 h-2 bg-purple-400 rounded-full mr-3"></span>
                            <span>{project}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Profile Overview Tab */}
        {activeTab === 'profile' && (
          <div className="space-y-8">
            <h2 className="text-2xl font-bold text-center">Profile Overview</h2>
            
            {profileOverview ? (
              <>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="bg-gray-800 rounded-lg p-6 text-center">
                    <h3 className="text-lg font-medium mb-2">Resume Strength</h3>
                    <p className="text-3xl font-bold text-blue-400">
                      {profileOverview.resume ? profileOverview.resume.strength_score.toFixed(1) : 'N/A'}/10
                    </p>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-6 text-center">
                    <h3 className="text-lg font-medium mb-2">Available Jobs</h3>
                    <p className="text-3xl font-bold text-green-400">{profileOverview.available_jobs}</p>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-6 text-center">
                    <h3 className="text-lg font-medium mb-2">Test Average</h3>
                    <p className="text-3xl font-bold text-purple-400">
                      {profileOverview.test_performance.average_score.toFixed(1)}%
                    </p>
                  </div>
                </div>

                {profileOverview.resume && (
                  <div className="bg-gray-800 rounded-lg p-6">
                    <h3 className="text-xl font-bold mb-4">Your Skills</h3>
                    <div className="flex flex-wrap gap-2">
                      {profileOverview.resume.tech_stacks.map((skill, index) => (
                        <span key={index} className="px-3 py-1 bg-blue-600 rounded-full text-sm">
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="text-center">
                  <button
                    onClick={() => alert('PDF report generation feature coming soon!')}
                    className="bg-green-600 hover:bg-green-700 px-8 py-3 rounded-lg font-medium text-lg transition-colors"
                  >
                    📥 Download Full Report
                  </button>
                </div>
              </>
            ) : (
              <div className="text-center py-12">
                <p className="text-xl text-gray-400">Loading profile overview...</p>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 border-t border-gray-700 mt-16">
        <div className="container mx-auto px-4 py-6 text-center text-gray-400">
          <p>&copy; 2025 IBM Quantum Jobs Tracker. Built for Hackathon Demo.</p>
        </div>
      </footer>
    </div>
  );
}

export default App;