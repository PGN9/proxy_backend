// Sample data
const sampleComments = [
  {
    id: 1,
    author: "healthseeker_22",
    subreddit: "health",
    comment: "I've been struggling with chronic back pain for months. Traditional treatments haven't worked, and I'm looking for alternative approaches that actually help.",
    votes: 47,
    emotion: "frustrated",
    timestamp: "2 hours ago"
  },
  {
    id: 2,
    author: "fitness_journey",
    subreddit: "fitness",
    comment: "My doctor recommended physical therapy, but I'm not seeing results after 6 weeks. Has anyone found specific exercises that actually work for lower back issues?",
    votes: 23,
    emotion: "negative",
    timestamp: "4 hours ago"
  },
  {
    id: 3,
    author: "patient_advocate",
    subreddit: "wellness",
    comment: "The healthcare system is so frustrating. I've been to 5 different specialists and still don't have clear answers about my condition. Anyone else dealing with this?",
    votes: 91,
    emotion: "frustrated",
    timestamp: "6 hours ago"
  },
  {
    id: 4,
    author: "yoga_enthusiast",
    subreddit: "wellness",
    comment: "Finally found relief through a combination of yoga and meditation. It took months of consistent practice, but my anxiety levels have significantly decreased.",
    votes: 156,
    emotion: "positive",
    timestamp: "8 hours ago"
  },
  {
    id: 5,
    author: "runner_mom",
    subreddit: "fitness",
    comment: "Started running again after my injury. Taking it slow but feeling optimistic about getting back to my previous fitness level.",
    votes: 34,
    emotion: "positive",
    timestamp: "12 hours ago"
  },
  {
    id: 6,
    author: "chronic_warrior",
    subreddit: "chronicpain",
    comment: "Some days are harder than others, but I'm learning to manage my condition better. Support groups have been incredibly helpful.",
    votes: 78,
    emotion: "neutral",
    timestamp: "1 day ago"
  },
  {
    id: 7,
    author: "wellness_seeker",
    subreddit: "health",
    comment: "Looking for recommendations on natural supplements for joint health. Has anyone had success with turmeric or glucosamine?",
    votes: 29,
    emotion: "neutral",
    timestamp: "1 day ago"
  },
  {
    id: 8,
    author: "mindful_living",
    subreddit: "wellness",
    comment: "Mindfulness practices have transformed my relationship with stress. It's not about eliminating stress but changing how we respond to it.",
    votes: 203,
    emotion: "positive",
    timestamp: "2 days ago"
  }
];

// ── NICHE MAPPING ─────────────────────────────────────────────
const nicheMap = {
  happy: [
    "Happy","Optimistic","Trusting","Peaceful","Powerful","Accepted","Proud",
    "Interested","Content","Hopeful","Inspired","Intimate","Loving","Thankful",
    "Sensitive","Creative","Courageous","Respected","Valued","Confident",
    "Successful","Curious","Inquisitive","Joyful","Free","Cheeky","Aroused",
    "Energetic","Eager"
  ],
  surprised: [
    "Excited","Amazed","Confused","Startled","Awe","Astonished",
    "Disillusioned","Dismayed","Shocked","Surprised"
  ],
  bad: [
    "Bad","Tired","Stressed","Busy","Bored","Sleepy","Overwhelmed",
    "Out of control","Restless","Apathetic","Indifferent"
  ],
  fearful: [
    "Fearful","Scared","Anxious","Insecure","Weak","Rejected","Threatened",
    "Helpless","Frightened","Worried","Overwhelmed","Inferior","Inadequate",
    "Worthless","Insignificant","Excluded","Persecuted","Nervous","Exposed"
  ],
  angry: [
    "Angry","Let down","Humiliated","Bitter","Mad","Aggressive","Frustrated",
    "Distant","Critical","Resentful","Disrespected","Ridiculed","Indignant",
    "Violated","Furious","Jealous","Provoked","Hostile","Infuriated","Annoyed",
    "Withdrawn","Numb","Sceptical"
  ],
  disgusted: [
    "Disgusted","Disapproving","Disappointed","Awful","Repelled","Judgmental",
    "Embarrassed","Appalled","Revolted","Awkward","Dismissive"
  ],
  sad: [
    "Sad","Lonely","Vulnerable","Despair","Guilty","Depressed","Hurt",
    "Abandoned","Victimized","Fragile","Grief","Powerless","Ashamed",
    "Empty","Remorseful","Inferior","Embarrassed"
  ]
};

// State management
let currentData = [...sampleComments];
let activeSubredditFilter = 'all';
let activeEmotionFilter = 'all';
let activeNicheFilter = 'all';
let activeSidebarSection = 'Dashboard';
let isScrapingInProgress = false;
let scrapingInterval = null;
let usingPreviousData = false;

// DOM elements
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebarOverlay');
const sidebarItems = document.querySelectorAll('.sidebar-item');
const subredditFilters = document.getElementById('subredditFilters');
const emotionFilters = document.getElementById('emotionFilters');
const nicheEmotionFilters = document.getElementById('nicheEmotionFilters');
const runBtn = document.getElementById('runBtn');
const clearBtn = document.getElementById('clearBtn');
const usePreviousDataBtn = document.getElementById('usePreviousDataBtn');
const tableBody = document.getElementById('tableBody');
const visibleCount = document.getElementById('visibleCount');
const totalCount = document.getElementById('totalCount');
const progressSection = document.getElementById('progressSection');
const progressFill = document.getElementById('progressFill');
const estimatedTime = document.getElementById('estimatedTime');
const filtersSection = document.getElementById('filtersSection');
const nicheFiltersSection = document.getElementById('nicheFiltersSection');

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
  setupEventListeners();
  populateNicheFilters('all');
  renderTable();
  updateStats();
  updateEstimatedTime();
});

// Event listeners
function setupEventListeners() {
  // Mobile menu toggle
  mobileMenuBtn.addEventListener('click', toggleMobileMenu);
  sidebarOverlay.addEventListener('click', closeMobileMenu);
  
  // Sidebar navigation
  sidebarItems.forEach(item => {
    item.addEventListener('click', () => handleSidebarClick(item));
  });
  
  // Filter buttons
  subredditFilters.addEventListener('click', handleSubredditFilter);
  emotionFilters.addEventListener('click', handleEmotionFilter);
  nicheEmotionFilters.addEventListener('click', handleNicheFilter);

  // Action buttons
  runBtn.addEventListener('click', handleRunAnalysis);
  clearBtn.addEventListener('click', handleClear);
  usePreviousDataBtn.addEventListener('click', handleUsePreviousData);
  
  // Form inputs
  const inputs = document.querySelectorAll('input');
  inputs.forEach(input => {
    input.addEventListener('input', handleInputChange);
  });
  
  // Window resize
  window.addEventListener('resize', handleResize);
}

// Mobile menu functions
function toggleMobileMenu() {
  sidebar.classList.toggle('open');
  sidebarOverlay.classList.toggle('show');
}

function closeMobileMenu() {
  sidebar.classList.remove('open');
  sidebarOverlay.classList.remove('show');
}

function handleResize() {
  if (window.innerWidth > 1024) {
    closeMobileMenu();
  }
}

// Sidebar navigation
function handleSidebarClick(item) {
  // Remove active class from all items
  sidebarItems.forEach(i => i.classList.remove('active'));
  
  // Add active class to clicked item
  item.classList.add('active');
  
  // Update active section
  activeSidebarSection = item.dataset.section;
  
  // Close mobile menu if open
  closeMobileMenu();
  
  // You can add section-specific logic here
  console.log(`Switched to section: ${activeSidebarSection}`);
}

// Estimated time calculation
function calculateEstimatedTime() {
  const subredditsInput = document.getElementById('subreddits').value;
  const numPostsInput = document.getElementById('numPosts').value;
  
  if (!subredditsInput || !numPostsInput) {
    return 0;
  }
  
  const subreddits = subredditsInput.split(',').map(s => s.trim()).filter(s => s.length > 0);
  const numPosts = parseInt(numPostsInput) || 0;
  
  // 10 seconds per post
  const totalSeconds = subreddits.length * numPosts * 10;
  return totalSeconds;
}

function formatTime(seconds) {
  if (seconds < 60) {
    return `${seconds}s`;
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return remainingSeconds > 0 ? `${minutes}min ${remainingSeconds}s` : `${minutes}min`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return minutes > 0 ? `${hours}hr ${minutes}min` : `${hours}hr`;
  }
}

function updateEstimatedTime() {
  const totalSeconds = calculateEstimatedTime();
  const timeText = totalSeconds > 0 ? formatTime(totalSeconds) : '0min';
  estimatedTime.textContent = `Estimated Completion Time: ${timeText}`;
}

function handleInputChange(e) {
  updateEstimatedTime();
  console.log(`Input changed: ${e.target.id} = ${e.target.value}`);
}

// Use Previous Data functionality
function handleUsePreviousData() {
  usingPreviousData = true;
  
  // Enable filters
  enableFilters();
  
  // Update button appearance
  usePreviousDataBtn.style.background = 'linear-gradient(135deg, #059669 0%, #047857 100%)';
  usePreviousDataBtn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M20 6L9 17l-5-5"></path>
    </svg>
    Using Previous Data
  `;
  
  console.log('Using previous data - filters enabled');
}

// Filter functions
function handleSubredditFilter(e) {
  if (e.target.classList.contains('filter-btn')) {
    // Remove active class from all subreddit filters
    subredditFilters.querySelectorAll('.filter-btn').forEach(btn => {
      btn.classList.remove('active');
    });
    
    // Add active class to clicked filter
    e.target.classList.add('active');
    
    // Update active filter
    activeSubredditFilter = e.target.dataset.filter;
    
    // Apply filters and re-render
    applyFilters();
  }
}

// ── BUILD NICHE BUTTONS ───────────────────────────────────────
function populateNicheFilters(category) {
  nicheEmotionFilters.innerHTML = '';
  // "All" button
  const allBtn = document.createElement('button');
  allBtn.className = 'filter-btn active';
  allBtn.dataset.niche = 'all';
  allBtn.textContent = 'All';
  nicheEmotionFilters.appendChild(allBtn);

  if (category !== 'all' && nicheMap[category]) {
    nicheMap[category].forEach(niche => {
      const btn = document.createElement('button');
      btn.className = 'filter-btn';
      btn.dataset.niche = niche.toLowerCase().replace(/\s+/g, '');
      btn.textContent = niche;
      nicheEmotionFilters.appendChild(btn);
    });
  }
  activeNicheFilter = 'all';
}

function handleNicheFilter(e) {
  if (!e.target.classList.contains('filter-btn')) return;
  nicheEmotionFilters.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  e.target.classList.add('active');
  activeNicheFilter = e.target.dataset.niche;
  applyFilters();
}

function handleEmotionFilter(e) {
  if (e.target.classList.contains('filter-btn')) {
    // Remove active class from all emotion filters
    emotionFilters.querySelectorAll('.filter-btn').forEach(btn => {
      btn.classList.remove('active');
    });
    
    // Add active class to clicked filter
    e.target.classList.add('active');
    
    // Update active filter
    activeEmotionFilter = e.target.dataset.emotion;

    // Repopulate niche filters for this category
    populateNicheFilters(activeEmotionFilter);
    
    // Apply filters and re-render
    applyFilters();
  }
}

function applyFilters() {
  let filteredData = [...sampleComments];
  
  // Apply subreddit filter
  if (activeSubredditFilter !== 'all') {
    filteredData = filteredData.filter(comment => 
      comment.subreddit === activeSubredditFilter
    );
  }
  
  // Apply emotion category filter
  if (activeEmotionFilter !== 'all') {
    filteredData = filteredData.filter(comment => 
      comment.emotion === activeEmotionFilter
    );
  }

  // Apply niche emotion filter
  if (activeNicheFilter !== 'all') {
    filteredData = filteredData.filter(c =>
      c.comment.toLowerCase().includes(activeNicheFilter)
    );
  }
  
  currentData = filteredData;
  renderTable();
  updateStats();
}

// Enable/disable filters
function enableFilters() {
  filtersSection.classList.remove('disabled');
  nicheFiltersSection.classList.remove('disabled');
}

function disableFilters() {
  filtersSection.classList.add('disabled');
  nicheFiltersSection.classList.add('disabled');
}

// Progress bar functions
function showProgressBar() {
  progressSection.style.display = 'flex';
}

function hideProgressBar() {
  progressSection.style.display = 'none';
  progressFill.style.width = '0%';
}

function updateProgress(percentage) {
  progressFill.style.width = `${Math.min(100, Math.max(0, percentage))}%`;
}

// Action button handlers
function handleRunAnalysis() {
  const subreddits = document.getElementById('subreddits').value;
  const numPosts = document.getElementById('numPosts').value;
  
  if (!subreddits || !numPosts) {
    alert('Please fill in both subreddits and number of posts.');
    return;
  }
  
  console.log('Running analysis with:', {
    subreddits,
    numPosts
  });
  
  // Start scraping process
  startScraping();
}

async function startScraping() {
  if (isScrapingInProgress) return;
  isScrapingInProgress = true;
  usingPreviousData = false;

  resetUsePreviousDataButton();
  disableFilters();
  showProgressBar();

  runBtn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M21 12a9 9 0 11-6.219-8.56"/>
    </svg>
    Scraping...
  `;
  runBtn.disabled = true;

  const totalSeconds = calculateEstimatedTime();
  let currentProgress = 0;
  const maxFakeProgress = 95; // cap fake progress at 95% until backend says done
  const progressIncrement = maxFakeProgress / (totalSeconds / 0.5); // update every 500ms

  // Start fake progress interval
  scrapingInterval = setInterval(() => {
    currentProgress += progressIncrement;
    if (currentProgress > maxFakeProgress) {
      currentProgress = maxFakeProgress;
    }
    updateProgress(currentProgress);
  }, 500);

  // Call backend to run scraping
  const subreddits = document.getElementById('subreddits').value;
  const numPosts = document.getElementById('numPosts').value;

  try {
    // Example: POST request to backend API
    const response = await fetch('http://127.0.0.1:5000/scrape_comments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subreddits, numPosts })
    });

    if (!response.ok) throw new Error('Network response was not ok');

    // Backend is done, so clear fake progress interval, jump to 100% and complete
    clearInterval(scrapingInterval);
    scrapingInterval = null;

    updateProgress(100);

    // You could get data from backend here instead of using sampleComments
    // const data = await response.json();
    // currentData = data.comments;  // or whatever structure your backend sends

    completeScraping();

  } catch (error) {
    clearInterval(scrapingInterval);
    scrapingInterval = null;
    isScrapingInProgress = false;
    runBtn.disabled = false;
    updateProgress(0);
    alert('Failed to scrape data: ' + error.message);
  }
}

function completeScraping() {
  // Clear interval
  if (scrapingInterval) {
    clearInterval(scrapingInterval);
    scrapingInterval = null;
  }
  
  // Reset state
  isScrapingInProgress = false;
  
  // Hide progress bar after a short delay
  setTimeout(() => {
    hideProgressBar();
  }, 1000);
  
  // Enable filters
  enableFilters();
  
  // Reset button state
  runBtn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polygon points="5,3 19,12 5,21 5,3"></polygon>
    </svg>
    Run Scraping
  `;
  runBtn.disabled = false;
  
  // You would typically make an API call here and update the data
  // For demo purposes, we'll just refresh the current data
  applyFilters();
  
  console.log('Scraping completed!');
}

function resetUsePreviousDataButton() {
  usePreviousDataBtn.style.background = 'linear-gradient(135deg, #10b981 0%, #059669 100%)';
  usePreviousDataBtn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M3 3h18v18H3zM9 9h6v6H9z"></path>
    </svg>
    Use Previous Data
  `;
}

function handleClear() {
  // Stop any ongoing scraping
  if (isScrapingInProgress) {
    if (scrapingInterval) {
      clearInterval(scrapingInterval);
      scrapingInterval = null;
    }
    isScrapingInProgress = false;
    runBtn.disabled = false;
    runBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="5,3 19,12 5,21 5,3"></polygon>
      </svg>
      Run Scraping
    `;
  }
  
  // Hide progress bar
  hideProgressBar();
  
  // Reset previous data state
  usingPreviousData = false;
  resetUsePreviousDataButton();
  
  // Disable filters
  disableFilters();
  
  // Clear inputs
  document.getElementById('subreddits').value = '';
  document.getElementById('numPosts').value = '';
  
  // Reset filters
  activeSubredditFilter = 'all';
  activeEmotionFilter = 'all';
  activeNicheFilter = 'all';
  
  // Reset filter buttons
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  
  document.querySelector('[data-filter="all"]').classList.add('active');
  document.querySelector('[data-emotion="all"]').classList.add('active');
  
  // Reset niche filters
  populateNicheFilters('all');
  
  // Update estimated time
  updateEstimatedTime();
  
  // Apply filters
  applyFilters();
}

// Table rendering
function renderTable() {
  if (currentData.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; padding: 2rem; color: #64748b;">
          No comments found matching your filters.
        </td>
      </tr>
    `;
    return;
  }
  
  tableBody.innerHTML = currentData.map(comment => `
    <tr>
      <td class="author-cell">u/${escapeHtml(comment.author)}</td>
      <td class="subreddit-cell">r/${escapeHtml(comment.subreddit)}</td>
      <td class="comment-cell">${escapeHtml(comment.comment)}</td>
      <td class="votes-cell">${comment.votes}</td>
      <td class="emotion-cell">
        <span class="emotion-badge emotion-${comment.emotion}">
          ${getEmotionIcon(comment.emotion)} ${capitalizeFirst(comment.emotion)}
        </span>
      </td>
      <td class="time-cell">${escapeHtml(comment.timestamp)}</td>
    </tr>
  `).join('');
}

function updateStats() {
  visibleCount.textContent = currentData.length;
  totalCount.textContent = sampleComments.length;
}

// Utility functions
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function capitalizeFirst(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function getEmotionIcon(emotion) {
  const icons = {
    positive: '😊',
    negative: '😞',
    neutral: '😐',
    frustrated: '😤'
  };
  return icons[emotion] || '😐';
}

// Add some sample interaction animations
document.addEventListener('DOMContentLoaded', function() {
  // Add subtle animations to cards on scroll
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  };
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, observerOptions);
  
  // Observe all sections
  document.querySelectorAll('.search-section, .filters-section, .data-section').forEach(section => {
    section.style.opacity = '0';
    section.style.transform = 'translateY(20px)';
    section.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(section);
  });
});
