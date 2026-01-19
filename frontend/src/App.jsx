import { useState } from 'react';
import PipeLineLander from './components/PipeLineLander';
import Visualizer from './components/Visualizer';
import Weightage from './components/Weightage';
import Team from './components/Team';
import weightIcon from './assets/weight.png';
import barIcon from './assets/pipeline.png';
import userIcon from './assets/user.png';
import visualizeIcon from './assets/visualize.png';
import './App.css';

function App() {
  const [view, setView] = useState('pipeline');

  return (
    <>
      <div className="intro-buttons">
        <button className="icon-button" onClick={() => setView('visualize')}>
            <img src={visualizeIcon} alt="Visualize" />
          </button>
        <button className="icon-button" onClick={() => setView('pipeline')}>
          <img src={barIcon} alt="Pipeline" />
        </button>
        <button className="icon-button" onClick={() => setView('weightage')}>
          <img src={weightIcon} alt="Weightage" />
        </button>
        <button className="icon-button" onClick={() => setView('team')}>
          <img src={userIcon} alt="Team" />
        </button>
      </div>

      <div className="view-container">
        {view === 'visualize' && <Visualizer key="visualize" />}
        {view === 'pipeline' && <PipeLineLander key="pipeline" />}
        {view === 'weightage' && <Weightage key="weightage" />}
        {view === 'team' && <Team key="team" />}        
      </div>
    </>
  );
}

export default App;
