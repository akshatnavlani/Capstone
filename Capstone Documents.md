# Understanding

# **Overview:**

This project works on influencer-brand mapping, what does that mean, it means given a budget of X thousand rupees, we need to map which influencer or collection of influencers a brand can approach to maximize their ROI/ Views per rupee for the sponsorship. We need to help brands select influencers that are trusted, relaible, have a good following. This project aims to help new and upcoming creators get brand deals, help veteran and famous creators reach the right brands and help brands value the creator accordingly.

A brand has 2 way of promoting a product:

* Barter: The brand does not pay the influencer but lets them keep the product  
* The company pays the influencer for a promotion

In this project we will be focusing on the latter.

Our end goal in this project is to create an interface where brands tell us what product they want to promote, what their budget is, what region/demographic they are trying to promote in,etc and our model gives them the top picks for their product. We also score top 10-15 influencers and assign them a score out of 100 based on multiple factors.

We also want to deal with spillover effects, that is if an influencer is endorsed by a brand, a friend of theirs who regularly is in videos with them has a good change that the friends viewers will also come to our subjects page and increase our reach.

## **HLD of the Project:**

Pasted image 20260719212914.png

---

# **Phases of the project:**

Data Collection  
 Edge Pre-processing  
 Dual Framework Setup  
 Fusion Layer  
 Application Layer

---

# **Data Collection:**

## **What data do we need:**

We need approximately 5-10k datapoints/entity/influencer and brands and their data across platforms.  
 Let's say for an athelete like lebron james, we need:

* Data from his accounts and accounts that are related to him like @kingJames(Instagram), @LeBron(Youtube) @Lakers(Instagram and Youtube) @r/nba,r/lebron,r/NBATalk (Reddit) and @KingJames (Twitter) and other accounts and pages related to LeBron  
* The follow count and posts and metrics on those post like like share and comments, will give us an idea to how many people will our product reach  
* Comments, subreddits, and discussion forums tell us the public perception of the influencer, performing a sentiment analysis, gives us a clear idea if the influencers image matches with what the brand is looking for  
* The age of the accounts and the followers help us detect if the account is actual or a fake, or if the followers are fake bots.  
* Timestamps of the posts, so that we can calculate temporal data, that will help us determine if posting the same or multiple pieces of content across platforms in a time gap has anything to do with how the internet reacts to it.  
* Thumbnails of videos  
* We will be skipping twitter as of now, because of api costs, might add later.

We need data not only from big athletes, we need data for athletes, brands,teams, leagues, Fitness influencers and lifestyle influencers. Any influencer with more than 5k followers can be included.

The newer the data the better, preferably last 6 months, that is January 2026 to June 2026\.

## **How do we collect this data:**

The most difficult part is to collect this data, as different platforms seem to have different policies, and since we have no budget to collect this data, we need to use what ever is free.

### **Option 1:**

* For youtube we can easily get it using youtube APIs.  
* Platforms like Instagram, Twitter and Reddit dont allow for direct or free scraping, so we can use tools like APIfy free tier to scrape this data  
* We need to create automations that can collect the required data and upload them to our database, we can use Agents like Hermes or n8n workflows that run automatically to accomplish this.

### **Option 2:**

* Youtube can be scraped  
* Other platforms, out of let's say 10k influencers, 2-3k can be scraped, rest can by synthesized, but this could fail as data could not be grounded and biased

### **Option 3 (Least favourable):**

* We can pay and scape the data

## **How do we store this data:**

We need a systemized way to store this data, a proper structured databse, which will help us make the optimization and preprocessing of data easier, we nee to store the data in such a way that it can be stored on cloud, accessed through API.

First of all we need a seed table that has the details of the influencer:

* Table 1 has their unique\_id, name, their official accounts on multiple platforms, accounts they are related to, their previous brand endorsements.  
* Table 2, i.e., Instagram Table has the Instagram data for multiple influencers, it has the creator unique\_id connecting it to table 1, has their post, posts description, comments and metrics  
* Table 3 is Youtube Table, which has the youtube data  
* Table 4 is twitter and Table 5 is reddit and so on

Note

Table structure may change as needed, this is not a set structure

We need a way to host/store this data in such a way that we can train our model with it

Todo

Create a finalized schema of the Database, choose which type of db to use, manage tables as required, initialize an empty DB where we can start storing data

## **How do we manage the model:**

One of the issues we will be facing is if we have any updates in the data in the future, like adding 5k new influencers, it would require us to retrain the whole model, can we avoid that, what is the best way to store the data.

Can we use Graph Neural Networks to counteract this, let’s say if any new nodes are added to our can our graphML model, without intensive retraining inculcate those new data points? 

---

# **Edge Pre-processing:**

In this phase we will be focusing on preprocessing the data we collected earlier. Here is what we need to do:

## **Basic Preprocessing:**

1. Temporal Normalization: Convert all timestamps to UTC  
2. Text Scrubbing: Remove URL parts, HTML tags and mentions from textual data to give BERT better embeddings  
3. Sponsorship Labeling: Standardized disclosure tags (e.g., \#ad, \#sponsored) into a binary is\_sponsored column to serve as the "Treatment" labels for the GAIL model.  
4. Metric Scaling: Applied log-transformations to highly skewed numerical data (like subscriber\_count and total\_views) to prevent mega-influencers from biasing the Graph Neural Network.

## **Module1: Fake Information Detection:**

We need scripts to filter out and remove accounts from out dataset that that seem to be bot accounts, have fake/bot followers and need to confirm if the account in question is actually of the influencer or not

## **Module 2: Sentiment Analysis:**

From all the reddit data, comments etc we can get a public view of the influencer, which can help us score them more accurately, it will help us analyze the comments, the discussions about an artist to get to know about their following, whom do they influence and does the artist and their content align with the company

## **Module3: Feature Extraction:**

We can use CLIP \+ BERT to extract creator features like CLIP for their thumbnails for colors, composition, scene type, production quality and BERT to know their topics, tone, brand mentions, writing style

## **Module 4: Cross-Platform Linking:**

Gives us an Idea of how many creators are on multiple platforms, increasing their reach, their influence  
 Remove duplicate creators, fan-pages etc.

## **Expected Output:**

A clean dataset that can be used to train ML models and Neural Networks for this project.

---

# **Dual Framework Setup:**

## **Graph Adaptive Inference Learning(GAIL) Model Training:**

Read Gail and its prerequisites and Working of GAIL to understand Gail.

Todo

Ground check if gail is a possibility or not, and then make a plan for implementation

## **Cross-Platform Temporal Analysis:**

This is where we check timestamps of the posts, so that we can calculate temporal data, that will help us determine if posting the same or multiple pieces of content across platforms in a time gap has anything to do with how the internet reacts to it.

We need to perform data analysis first and check if any such relation is found, if it is found the we need to figure out a way to implement it.

Caution

Needs to be ground checked and implementation needs to be thought.

## **Causal Inference:**

Now that we have information from GAIL and Temporal analysis we need to se what inference can we derive from our setup, we need a ground reality check, and need to decide what features actually play a role in an influencers role and optimize our process.

---

# **Fusion Layer:**

Results from our Dual-Framework setup are now here used to create a final multi-modal model which will be the heart of our project, this model uses the results from its upper layers, adjusts it for risks, creates a boundary between halucination and reality.

This layer is what will provide us with our ROI aggregator, that will be calculated through our final scores and attributes of the influencers.

Caution

Needs to be ground checked and implementation needs to be thought.

---

# **Application Layer**

This will be the final application layer where the fusion layer works as the main engine to provide our app with features like:

* Recommendation Engine: Influencer ranking and ROI Breakdown  
* Monitoring and alerts: Risk Flag and Sentiment Alerts  
  * Like if an influencer made a controversial statement or said something that hurt people, our system must flag it and adjust the score accordingly  
* Explainability Network: Network Visualization and Causal Insights  
  * We should be able to see a graph of all influencers and brands, of how they are connected, causal insights like if posting at a specific time results in a better reach and other such outcomes  
     Note

     Need to decide on a solid tech stack that can be hosted online, possibly docerize the app and be able to ship it at the end.

# Gail Pre-requisites

# GAIL: Graph-Adaptive Interference Learning

## Prerequisites and Concept Guide

# Overview: GAIL in 5 Sentences

* When a brand sponsors an influencer, their collaborators also benefit from "spillover effects" \- but we don't know HOW MUCH each collaborator benefits.  
* Traditional methods assume all collaborators benefit equally or use simple formulas like "spillover \= 1/distance" \- but this is often wrong and leads to bad predictions.  
* GAIL uses Graph Neural Networks to LEARN which collaborators benefit most by analyzing thousands of past partnerships and discovering patterns.  
* It learns an "attention mechanism" that assigns personalized weights to each collaboration relationship, predicting specific engagement gains for neighbors.  
* This is novel as the first method to learn these patterns automatically while maintaining causal validity, leading to 40% better predictions.

# Level 1: Basic Concepts

## 1\. What is a Graph/Network?

**Simple Definition:** Nodes (dots) \= Things (influencers); Edges (lines) \= Connections (collaborations).  
**Example:** FitWithPriya — YogaGuru. This shows who has collaborated with whom.  
*5-minute primer: "Think of it like Facebook friend networks, but instead of friends, it's collaborations between influencers."*

## 2\. What is Causal Inference?

**Simple Definition:** Distinguishing between correlation and causation.  
**Example:** Correlation is ice cream and drowning both increasing in summer; Causation is aspirin making a headache go away.  
*5-minute primer: "Correlation is when two things happen together. Causation is when one thing MAKES the other happen."*

## 3\. What is Spillover/Interference?

**Simple Definition:** When treating one person affects another person.  
**Example:** Nike sponsors FitWithPriya, and YogaGuru (not sponsored) gets \+3K engagement anyway.  
*5-minute primer: "When you sponsor one influencer, their friends ALSO benefit indirectly. GAIL predicts exactly how much."*

# Level 2: Intermediate Concepts

## 4\. What are Embeddings?

**Simple Definition:** Turning complex things into lists of numbers that capture their "essence."  
**Example:** FitWithPriya might be \[0.9 fitness, 0.8 gym\], while YogaGuru is \[0.7 fitness, 0.9 yoga\].  
*5-minute primer: "Every influencer gets a 'fingerprint' of numbers. Similar fingerprints \= high spillover."*

## 5\. What is Machine Learning/Neural Networks?

**Simple Definition:** The computer learns patterns from examples, like a child learning.  
*5-minute primer: "Instead of telling the computer 'how spillover works', we show it examples and it figures it out automatically."*

## 6\. What is Attention Mechanism?

**Simple Definition:** Deciding "which parts are important" automatically.  
*5-minute primer: "Like how you pay more attention to some friends' advice, GAIL learns which collaborations 'matter more'."*

## 7\. What is Exposure Mapping?

**Simple Definition:** Measuring "how much is someone exposed to a treatment through their network?"  
**Example:** If YogaGuru has 1 sponsored neighbor out of 3, traditional exposure is 1/3. GAIL uses attention (e.g., 0.7 weight) for a personalized measure.  
*5-minute primer: "Exposure measures 'how much treatment reaches you through your network'. GAIL learns the best way to measure this."*

# Level 3: Advanced Concepts

## 8\. What is Joint Optimization?

**Simple Definition:** Learning two things at the same time so they work well together.  
*5-minute primer: "Like learning to ride a bike and steer at the same time, GAIL learns exposure and causal effects together."*

## 9\. What is Causal Regularization?

**Simple Definition:** Adding "common sense rules" to prevent the model from learning nonsense.  
*5-minute primer: "Like adding guardrails so the model doesn't learn crazy patterns \- it forces the model to learn things that make causal sense."*

## 10\. What is Identifiability?

**Simple Definition:** Can we figure out the TRUE causal effect from the data we have?  
*5-minute primer: "Identifiability means 'can we actually measure the real causal effect?' GAIL proves mathematically that it can."*

# How to Explain GAIL: Scripts

## Script 1: For a Non-Technical Friend

"You know how when a celebrity endorses a product, their friends' careers also get a boost? That's spillover. GAIL is a smart system that predicts exactly how much each friend will benefit. It's 40% more accurate than traditional methods."

## Script 2: For a Technical Friend (CS Background)

"It's a method that uses Graph Neural Networks with attention mechanisms to learn heterogeneous exposure functions. It jointly optimizes exposure learning and causal estimation with a multi-objective loss and causal regularization."

## Script 3: For a Research-Oriented Audience

"We're extending network causal inference to settings where the interference mechanism is unknown. We parameterize exposure using GNN \+ attention and prove consistency of the learned exposure estimator, deriving sample complexity bounds."

# Working of GAIL

# GAIL: How It Works \- Step-by-Step Guide

# Phase 1: Preparation

## Step 1: Collect Historical Data

Gather past brand partnerships to observe real-world outcomes. Unlike traditional causal inference where humans assume the spillover mechanism, GAIL learns it from the data.

* **Traditional Causal Inference:** Manually decide spillover factors (e.g., distance) and estimate using fixed formulas.  
* **GAIL:** The system learns "What causes spillover?" from patterns in the data.

**Example Data:**

* **Partnership 1:** Nike sponsored FitWithPriya (engagement 45K → 60K).  
  * YogaGuru (Collaborator): 30K → 33K (gained 3K)  
  * GymBro (Collaborator): 25K → 33K (gained 8K)  
  * FashionBlogger (Collaborator): 20K → 20.3K (gained 0.3K)

## Step 2: Build the Collaboration Network

Create a graph where influencers are nodes and collaborations are edges. This map records who got sponsored (treatment), their engagement (direct effect), and their collaborators' engagement (spillover).  
**Network Map Example:**

* **FitWithPriya connects to:** YogaGuru (8 collabs), GymBro (5 collabs), FashionBlogger (2 collabs).  
* **YogaGuru connects to:** FitWithPriya (8 collabs), MeditationMaster (10 collabs), WellnessQueen (6 collabs).

## Step 3: Extract Creator Features

Gather characteristics for each creator across three main dimensions:

* **Visual Features (CLIP):** Thumbnail style, colors, composition, and production quality.  
* **Text Features (BERT):** Content themes, topics, tone, and writing style.  
* **Metadata:** Subscriber count, category (e.g., "Fitness"), engagement rate, and reputation score.

# Phase 2: Training GAIL

## Step 4: Initialize the Graph Neural Network (GNN)

The GNN begins with random initialization. It will learn how creators relate to each other and which features best indicate potential spillover.

## Step 5: Encode Creators into Embeddings

The GNN processes the graph to create a numerical "summary" or embedding for every creator. This embedding captures individual characteristics, network position, and community membership.

## Step 6: Learn Attention Weights (The Key Innovation\!)

GAIL learns which collaborators are most affected when a specific node is sponsored. Instead of assuming all neighbors are equal, it uses embedding similarity to determine importance.  
***Example (FitWithPriya sponsored):***

* YogaGuru (Similar embedding) → High attention (0.35)  
* GymBro (Similar embedding) → High attention (0.55)  
* FashionBlogger (Different embedding) → Low attention (0.10)

## Step 7: Compute Learned Exposure

Calculate how "exposed" each creator is based on sponsored neighbors and attention weights.

## Step 8: Predict Spillover Effects

Use the learned pattern *spillover \= f(exposure, creator\_features)* to predict engagement changes. High exposure plus similar content typically results in larger spillover.

## Step 9: Compare Predictions to Reality

Check accuracy against historical data. For example: YogaGuru predicted \+3.2K, actual \+3K. Calculate the error to guide model adjustments.

## Step 10: Apply Causal Regularization

Ensure patterns make causal sense by enforcing rules:

* **Consistency:** No sponsored neighbors should result in zero exposure.  
* **Overlap:** Treatment probabilities shouldn't be extreme (0% or 100%).  
* **Smoothness:** Similar creators should have similar exposure patterns.  
* **Doubly Robust Correction:** Account for selection bias (e.g., brands favoring already-popular creators).

## Step 11: Update the Network (Learning)

Use gradient descent to minimize errors and penalties. GAIL learns lessons like: "Increase attention for very similar content" or "Emphasize community boundaries."

## Step 12: Repeat for All Historical Data

Iterate through thousands of partnerships. With each iteration, patterns like content similarity, community structure, and collaboration frequency become sharper and more reliable.

# Phase 3: Using GAIL for Predictions

## Step 13: Brand Recommendation Request

A brand asks: "Who should we sponsor to maximize ROI and total brand exposure?"

## Step 14: Simulate Different Scenarios

GAIL tests the outcomes of sponsoring different creators:

* **Scenario A (FitWithPriya):** Total Exposure: 33K; ROI: 0.41  
* **Scenario B (GymBro):** Total Exposure: 34K; ROI: 0.52  
* **Scenario C (FashionBlogger):** Total Exposure: 12K; ROI: 0.24

## Step 15: Make Recommendation

Based on simulations, GymBro is selected as the best choice due to the highest ROI and strongest network amplification.

## Step 16: Explain Why (Interpretability)

GAIL provides transparency:

* **Direct Impact:** High engagement and brand-content alignment.  
* **Network Insight:** High centrality within the target community (Fitness).  
* **Causal Mechanism:** Products reach audience through direct views and organic collaborator cross-promotion.

# Phase 4: Continuous Learning

## Step 17: Monitor Actual Results

Track real-world performance after the sponsorship. For GymBro: Actual total 33.7K engagement (predicted 34K), demonstrating 99% accuracy.

## Step 18: Update GAIL with New Data

Add the new campaign to the training set. GAIL reinforces successful patterns and makes minor weight adjustments based on any deviation from predictions.

4. End-to-End Learning 5\. Theoretically Grounded SUMMARY IN SIMPLE TERMS What GAIL does: Key Innovation: Instead of you deciding "spillover \= 1/distance", GAIL learns "spillover \= complex function of content similarity \+ network position \+ collaboration history" Why it's novel: Traditional ML: Learns "high followers → high effect" (correlation)GAIL: Learns "sponsored neighbor with similar content → high effect" (causation) Result: Predictions work even on new scenarios Traditional: Two-stage (estimate exposure, then estimate effects)GAIL: Joint learning (both at once, optimized together) Result: Errors don't compound, more efficient Traditional ML: Black box, no guaranteesGAIL: Causal regularization ensures identifiability Result: Can trust predictions for decision-making 1\. Looks at past brand partnerships 2\. Sees which influencers' collaborators benefited (spillover) 3\. Learns WHAT CAUSES spillover (not just correlations) 4\. Uses this learned knowledge to predict future partnerships First to LEARN exposure patterns (not hand-craft them) Maintains causal validity (not just prediction accuracy) Has theoretical guarantees (provably consistent)

# Summary in Simple Terms

GAIL looks at past partnerships, identifies which collaborators benefited (spillover), and learns the causal mechanics rather than simple correlations. This allows for accurate predictions and theoretically grounded decision-making for future brand campaigns.  
